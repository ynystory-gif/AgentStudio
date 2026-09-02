from __future__ import annotations

"""Standalone QLoRA worker used by AgentStudio's weight fine-tune job.

The worker is launched in a subprocess so CUDA memory and Hugging Face imports do not
pollute the FastAPI process. It supports two explicit phases:

  train -> qwen3.5 4B 4-bit QLoRA adapter
  merge -> load base model on CPU and fuse the adapter into independent Safetensors

Training data is text-only even though Qwen3.5 is multimodal. The vision path is not
used or trained; LoRA targets only language projection/MLP modules.
"""

import argparse
import json
import os
import sys
from pathlib import Path


def _bootstrap(package_dir: str) -> None:
    value = str(package_dir or "").strip()
    if value and value not in sys.path:
        sys.path.insert(0, value)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


def _emit(percent: int, message: str) -> None:
    print(f"PROGRESS|{max(0, min(100, int(percent)))}|{message}", flush=True)


def _load_processor_and_tokenizer(base_model: str):
    from transformers import AutoProcessor, AutoTokenizer

    processor = None
    tokenizer = None
    try:
        processor = AutoProcessor.from_pretrained(base_model, trust_remote_code=True)
        tokenizer = getattr(processor, "tokenizer", None)
    except Exception:
        processor = None
    if tokenizer is None:
        tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return processor, tokenizer


def _load_model(base_model: str, *, quantized: bool, cpu: bool = False):
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    common = {
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }
    if cpu:
        common.update({"device_map": "cpu", "torch_dtype": torch.float16})
    elif quantized:
        common.update({
            "device_map": {"": 0},
            "quantization_config": BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            ),
        })

    errors: list[str] = []
    # Qwen3.5-4B is currently exposed by Transformers as a multimodal model. Keep a
    # CausalLM fallback so the worker also works if a later Transformers release exposes
    # the text path directly through AutoModelForCausalLM.
    try:
        from transformers import AutoModelForMultimodalLM
        return AutoModelForMultimodalLM.from_pretrained(base_model, **common)
    except Exception as exc:
        errors.append(f"AutoModelForMultimodalLM: {exc}")
    try:
        return AutoModelForCausalLM.from_pretrained(base_model, **common)
    except Exception as exc:
        errors.append(f"AutoModelForCausalLM: {exc}")
    raise RuntimeError("Qwen3.5 모델을 불러오지 못했습니다.\n" + "\n".join(errors[-2:]))


def _chat_text(tokenizer, instruction: str, input_text: str, output: str = "", generation_prompt: bool = False) -> str:
    user = str(instruction or "").strip()
    context = str(input_text or "").strip()
    if context:
        user = f"{user}\n\n[입력/상황]\n{context}" if user else context
    messages = [{"role": "user", "content": user}]
    if output:
        messages.append({"role": "assistant", "content": str(output).strip()})
    if hasattr(tokenizer, "apply_chat_template") and getattr(tokenizer, "chat_template", None):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=bool(generation_prompt),
            )
        except Exception:
            pass
    if output:
        return f"User: {user}\nAssistant: {output}"
    return f"User: {user}\nAssistant:"


class _LearningDataset:
    def __init__(self, path: Path, tokenizer, max_length: int):
        self.rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            instruction = str(item.get("instruction") or "").strip()
            output = str(item.get("output") or "").strip()
            if not instruction or not output:
                continue
            prompt_text = _chat_text(tokenizer, instruction, str(item.get("input") or ""), generation_prompt=True)
            full_text = _chat_text(tokenizer, instruction, str(item.get("input") or ""), output=output)
            prompt_ids = tokenizer(prompt_text, add_special_tokens=False).input_ids
            full_ids = tokenizer(full_text, add_special_tokens=False).input_ids
            eos = tokenizer.eos_token_id
            if eos is not None and (not full_ids or full_ids[-1] != eos):
                full_ids = full_ids + [eos]
            full_ids = full_ids[:max_length]
            prompt_len = min(len(prompt_ids), len(full_ids))
            labels = [-100] * prompt_len + full_ids[prompt_len:]
            if not any(value != -100 for value in labels):
                continue
            self.rows.append({"input_ids": full_ids, "labels": labels, "attention_mask": [1] * len(full_ids)})
        if not self.rows:
            raise ValueError("토큰화 후 학습 가능한 예제가 없습니다.")

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]


class _Collator:
    def __init__(self, tokenizer):
        self.pad_id = int(tokenizer.pad_token_id or tokenizer.eos_token_id or 0)

    def __call__(self, features):
        import torch

        width = max(len(row["input_ids"]) for row in features)
        input_ids, attention, labels = [], [], []
        for row in features:
            pad = width - len(row["input_ids"])
            input_ids.append(row["input_ids"] + [self.pad_id] * pad)
            attention.append(row["attention_mask"] + [0] * pad)
            labels.append(row["labels"] + [-100] * pad)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def _train(args) -> None:
    import torch
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import Trainer, TrainerCallback, TrainingArguments

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU를 찾을 수 없습니다. QLoRA 가중치 학습은 NVIDIA CUDA GPU가 필요합니다.")

    _emit(2, "Qwen3.5 Processor/Tokenizer 다운로드 및 확인")
    processor, tokenizer = _load_processor_and_tokenizer(args.base_model)
    _emit(8, "Qwen3.5-4B를 4-bit NF4로 GPU에 로드")
    model = _load_model(args.base_model, quantized=True)
    if hasattr(model, "config"):
        model.config.use_cache = False

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    suffixes = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
    present = {name.rsplit(".", 1)[-1] for name, _ in model.named_modules()}
    targets = sorted(suffixes.intersection(present))
    if not targets:
        raise RuntimeError("Qwen3.5 언어 모델의 LoRA target module을 찾지 못했습니다.")

    lora = LoraConfig(
        r=int(args.lora_rank),
        lora_alpha=int(args.lora_alpha),
        lora_dropout=0.05,
        bias="none",
        target_modules=targets,
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora)
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    model.print_trainable_parameters()

    _emit(15, "검증 Dataset을 토큰화")
    dataset = _LearningDataset(Path(args.dataset), tokenizer, int(args.max_length))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    class ProgressCallback(TrainerCallback):
        def on_log(self, training_args, state, control, logs=None, **kwargs):
            if state.max_steps:
                percent = 20 + int(min(1.0, state.global_step / max(1, state.max_steps)) * 75)
                loss = (logs or {}).get("loss")
                suffix = f" · loss={loss}" if loss is not None else ""
                _emit(percent, f"QLoRA 학습 {state.global_step}/{state.max_steps}{suffix}")

    training_args = TrainingArguments(
        output_dir=str(output / "trainer"),
        num_train_epochs=float(args.epochs),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=int(args.gradient_accumulation),
        learning_rate=float(args.learning_rate),
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        logging_steps=1,
        save_strategy="no",
        report_to="none",
        fp16=True,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=_Collator(tokenizer),
        callbacks=[ProgressCallback()],
    )
    _emit(20, f"QLoRA 실제 가중치 학습 시작 · 예제 {len(dataset)}개")
    result = trainer.train()
    adapter = output / "adapter"
    adapter.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter), safe_serialization=True)
    tokenizer.save_pretrained(str(adapter))
    if processor is not None:
        try:
            processor.save_pretrained(str(adapter))
        except Exception:
            pass
    metrics = dict(result.metrics or {})
    (output / "training_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _emit(100, f"QLoRA Adapter 저장 완료 · {adapter}")


def _merge(args) -> None:
    from peft import PeftModel

    _emit(5, "Base Model을 CPU에 로드")
    processor, tokenizer = _load_processor_and_tokenizer(args.base_model)
    base = _load_model(args.base_model, quantized=False, cpu=True)
    _emit(35, "LoRA Adapter를 Base 가중치에 병합")
    model = PeftModel.from_pretrained(base, args.adapter, is_trainable=False)
    merged = model.merge_and_unload(safe_merge=True)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    _emit(70, "독립 Safetensors 모델 저장")
    merged.save_pretrained(str(output), safe_serialization=True, max_shard_size="4GB")
    tokenizer.save_pretrained(str(output))
    if processor is not None:
        try:
            processor.save_pretrained(str(output))
        except Exception:
            pass
    _emit(100, f"Base 없이 실행 가능한 Merge 모델 저장 완료 · {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["train", "merge"])
    parser.add_argument("--package-dir", default="")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--dataset", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--adapter", default="")
    parser.add_argument("--max-length", type=int, default=768)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--gradient-accumulation", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    args = parser.parse_args()
    _bootstrap(args.package_dir)
    if args.phase == "train":
        if not args.dataset:
            raise ValueError("--dataset is required for train")
        _train(args)
    else:
        if not args.adapter:
            raise ValueError("--adapter is required for merge")
        _merge(args)


if __name__ == "__main__":
    main()
