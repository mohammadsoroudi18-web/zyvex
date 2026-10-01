"""Project templates — scaffold real files into the project store."""
from __future__ import annotations

from .filesystem import FilesystemAdapter

TEMPLATES = {
    "empty": {"label": "Empty Project", "description": "A bare project with a README."},
    "react_vite_ts": {
        "label": "React + Vite + TypeScript",
        "description": "A Vite + React + TypeScript starter with a dashboard shell.",
    },
}


def template_catalog() -> list[dict]:
    return [{"id": key, **value} for key, value in TEMPLATES.items()]


def scaffold(project_id: str, template: str) -> list[dict]:
    """Create the template's real files. Returns the created paths."""
    adapter = FilesystemAdapter(project_id)
    created: list[str] = []

    if template == "react_vite_ts":
        files = {
            "package.json": """{
  "name": "nexora-app",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^6.0.3",
    "vitest": "^2.1.8"
  }
}
""",
            "vite.config.ts": """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: Number(process.env.PORT ?? 4100) },
});
""",
            "index.html": """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NEXORA App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""",
            "src/main.tsx": """import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
""",
            "src/App.tsx": """import { useState } from 'react';

interface Task {
  id: number;
  title: string;
  done: boolean;
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([
    { id: 1, title: 'Set up the dashboard', done: true },
    { id: 2, title: 'Add task management', done: false },
  ]);
  const [draft, setDraft] = useState('');

  function addTask() {
    if (!draft.trim()) return;
    setTasks([...tasks, { id: Date.now(), title: draft.trim(), done: false }]);
    setDraft('');
  }

  return (
    <main className="dashboard">
      <h1>Task Manager</h1>
      <div className="composer">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="New task"
        />
        <button onClick={addTask}>Add</button>
      </div>
      <ul>
        {tasks.map((task) => (
          <li key={task.id} className={task.done ? 'done' : ''}>
            {task.title}
          </li>
        ))}
      </ul>
    </main>
  );
}
""",
            "src/styles.css": """body {
  margin: 0;
  font-family: system-ui, sans-serif;
  background: #0f1117;
  color: #e6e8ee;
}
.dashboard {
  max-width: 640px;
  margin: 4rem auto;
  padding: 0 1.5rem;
}
.composer {
  display: flex;
  gap: 0.5rem;
  margin: 1rem 0;
}
input {
  flex: 1;
  padding: 0.6rem 0.75rem;
  border-radius: 6px;
  border: 1px solid #2a2f3a;
  background: #161922;
  color: inherit;
}
button {
  padding: 0.6rem 1rem;
  border-radius: 6px;
  border: 1px solid #3b4bff;
  background: #3b4bff;
  color: #fff;
  cursor: pointer;
}
.done {
  text-decoration: line-through;
  opacity: 0.5;
}
""",
            "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["src"]
}
""",
            "README.md": """# NEXORA App

React + Vite + TypeScript starter.

```bash
npm install
npm run dev
```
""",
        }
    else:
        files = {
            "README.md": "# New Project\n\nCreated with NEXORA AI Builder.\n",
            "src/index.py": "def main():\n    print('hello from NEXORA')\n\n\nif __name__ == '__main__':\n    main()\n",
        }

    for path, content in files.items():
        adapter.write(path, content)
        created.append(path)
    return created
