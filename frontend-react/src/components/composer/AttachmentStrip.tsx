import { useRef } from "react";
import { uploadFile, deleteFile } from "../../api/files";
import { useChatStore } from "../../store/chatStore";

const ACCEPTED = ".jpg,.jpeg,.png,.webp,.gif,.pdf,.txt,.csv,.json,.docx,.pptx,.xlsx";

export function AttachmentStrip() {
  const attachments = useChatStore((s) => s.attachments);
  const addAttachment = useChatStore((s) => s.addAttachment);
  const removeAttachment = useChatStore((s) => s.removeAttachment);
  const setError = useChatStore((s) => s.setError);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files) return;
    for (const file of Array.from(files)) {
      try {
        const uploaded = await uploadFile(file);
        addAttachment(uploaded);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      }
    }
  };

  const handleRemove = async (fileId: string) => {
    removeAttachment(fileId);
    await deleteFile(fileId).catch(() => null);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (attachments.length === 0) {
    return (
      <div className="flex items-center">
        <button
          type="button"
          aria-label="Attach files"
          className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors p-1 rounded"
          onClick={() => fileInputRef.current?.click()}
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
          </svg>
        </button>
        <input ref={fileInputRef} type="file" multiple accept={ACCEPTED} className="hidden" onChange={(e) => void handleFiles(e.target.files)} />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 flex-wrap pb-1">
      <button
        type="button"
        aria-label="Attach files"
        className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors p-1 rounded shrink-0"
        onClick={() => fileInputRef.current?.click()}
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
        </svg>
      </button>
      <input ref={fileInputRef} type="file" multiple accept={ACCEPTED} className="hidden" onChange={(e) => void handleFiles(e.target.files)} />
      <ul className="flex items-center gap-2 flex-wrap" aria-live="polite">
        {attachments.map((a) => (
          <li key={a.file_id} className="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-700 rounded-md px-2 py-1">
            <span className="text-xs text-zinc-600 dark:text-zinc-300 max-w-[120px] truncate" title={a.original_filename}>
              {a.original_filename}
            </span>
            <span className="text-[10px] text-zinc-400 dark:text-zinc-500">{formatSize(a.size_bytes)}</span>
            <button
              type="button"
              className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 ml-0.5 text-xs"
              aria-label={`Remove ${a.original_filename}`}
              onClick={() => void handleRemove(a.file_id)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
