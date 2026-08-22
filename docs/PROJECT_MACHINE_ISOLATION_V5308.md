# v5.308 Project Machine Isolation

## Problem

When multiple PCs use the same Supabase PostgreSQL runtime, the `projects` table was queried globally. A home PC could therefore see notebook/laptop project paths that only exist on the other machine.

## Fix

- Adds `projects.pc_name`.
- New projects automatically use the current `AGENTSTUDIO_PC_NAME`.
- Project list, open, favorite, external analysis lookup, duplicate-path checks, diagnostics, health counts and runtime allow-list restoration are scoped to the current PC.
- Legacy `pc_name=''` rows are claimed only when their exact `root_path` physically exists as a directory on the current PC. This prevents a newly connected PC from taking ownership of all historical shared rows.
- Global `root_path` uniqueness is replaced with `(pc_name, root_path)`.
- PC rename migrates project ownership together with machine settings.

## Shared Supabase behavior

The same Supabase database can contain projects from several PCs, but each AgentStudio instance receives only its own project's rows. Other PCs' rows remain in Supabase for their original machine and are not deleted.
