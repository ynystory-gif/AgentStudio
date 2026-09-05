const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const args = process.argv.slice(2)

function valueOf(name, fallback) {
  const index = args.indexOf(name)
  if (index >= 0 && index + 1 < args.length) return args[index + 1]
  return fallback
}

const host = valueOf('--host', '127.0.0.1')
const rawPort = valueOf('--port', '')
if (!rawPort) throw new Error('--port is required; SYSTEM_ADMIN must pass AGENTSTUDIO_FRONTEND_PORT from root .env')
const port = Number(rawPort)
const logPath = valueOf(
  '--log',
  path.resolve(__dirname, '..', 'logs', 'frontend_console.log')
)

fs.mkdirSync(path.dirname(logPath), { recursive: true })

function write(text) {
  const value = String(text || '')
  process.stdout.write(value)
  fs.appendFileSync(logPath, value, 'utf8')
}

let stopping = false
let child = null
let restartCount = 0
const maxRestarts = 20

function buildCommand() {
  const npmArgs = [
    'run',
    'dev',
    '--',
    '--host',
    host,
    '--port',
    String(port),
    '--strictPort'
  ]

  if (process.platform === 'win32') {
    const comspec = process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe'

    return {
      command: comspec,
      args: [
        '/d',
        '/s',
        '/c',
        'npm ' + npmArgs.map(arg => {
          if (/^[A-Za-z0-9_.:/-]+$/.test(arg)) return arg
          return `"${String(arg).replace(/"/g, '""')}"`
        }).join(' ')
      ]
    }
  }

  return {
    command: 'npm',
    args: npmArgs
  }
}

function start() {
  write(
    `\n[${new Date().toISOString()}] ` +
    `Frontend Vite start host=${host} port=${port}\n`
  )

  const env = {
    ...process.env,
    AGENTSTUDIO_FRONTEND_HOST: host,
    AGENTSTUDIO_FRONTEND_PORT: String(port)
  }

  const launch = buildCommand()

  try {
    child = spawn(
      launch.command,
      launch.args,
      {
        cwd: __dirname,
        env,
        stdio: ['inherit', 'pipe', 'pipe'],
        windowsHide: false
      }
    )
  } catch (error) {
    write(`[Frontend spawn failed] ${error.stack || error}\n`)
    scheduleRestart(1)
    return
  }

  child.stdout.on('data', data => write(data.toString()))
  child.stderr.on('data', data => write(data.toString()))

  child.on('error', error => {
    write(`[Frontend runner error] ${error.stack || error}\n`)
  })

  child.on('exit', (code, signal) => {
    write(
      `[${new Date().toISOString()}] ` +
      `Vite exited code=${code} signal=${signal || '-'}\n`
    )

    child = null

    if (stopping) {
      process.exit(code || 0)
      return
    }

    scheduleRestart(code || 1)
  })
}

function scheduleRestart(exitCode) {
  restartCount += 1

  if (restartCount > maxRestarts) {
    write(
      `[FAILED] Vite exceeded automatic restart limit: ${maxRestarts}\n`
    )
    process.exit(exitCode || 1)
    return
  }

  write(
    `[RECOVERY] Vite 자동 재시작 ${restartCount}/${maxRestarts} - 2초 후 재시작\n`
  )

  setTimeout(start, 2000)
}

function shutdown(signal) {
  stopping = true
  write(`[runner] received ${signal}; stopping Vite\n`)

  if (child && !child.killed) {
    try {
      if (process.platform === 'win32') {
        spawn(
          process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe',
          ['/d', '/s', '/c', `taskkill /PID ${child.pid} /T /F`],
          {
            stdio: 'ignore',
            windowsHide: true
          }
        )
      } else {
        child.kill('SIGTERM')
      }
    } catch {}
  } else {
    process.exit(0)
  }

  setTimeout(() => process.exit(0), 3000).unref()
}

process.on('SIGINT', () => shutdown('SIGINT'))
process.on('SIGTERM', () => shutdown('SIGTERM'))

process.on('uncaughtException', error => {
  write(`[runner uncaughtException] ${error.stack || error}\n`)
})

process.on('unhandledRejection', error => {
  write(`[runner unhandledRejection] ${error?.stack || error}\n`)
})

start()
