import { useChatStore } from "../../store/chatStore";

const EXAMPLES = [
  "Explain quantum computing in simple terms",
  "Write a haiku about artificial intelligence",
  "What are the pros and cons of remote work?",
  "Explain the difference between SQL and NoSQL databases",
  "What is the best way to learn a new programming language?",
];

export function ExampleChips() {
  const setPrompt = useChatStore((s) => s.setPrompt);
  const responses = useChatStore((s) => s.responses);
  const streaming = useChatStore((s) => s.streaming);

  if (responses.length > 0 || streaming) return null;

  return (
    <div className="flex flex-col items-center justify-center flex-1 py-12 px-4">
      <p className="text-[10px] font-semibold tracking-widest text-zinc-400 dark:text-zinc-500 uppercase mb-4">
        Try an example
      </p>
      <div className="flex flex-wrap justify-center gap-2 max-w-2xl">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            className="text-xs px-3 py-2 rounded-full bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:border-zinc-400 dark:hover:border-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200 transition-all shadow-sm"
            onClick={() => setPrompt(ex)}
            title={ex}
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
