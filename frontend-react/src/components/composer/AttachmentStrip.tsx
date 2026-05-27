import { useRef } from "react";
import { uploadFile, deleteFile } from "../../api/files";
import { useChatStore } from "../../store/chatStore";
import styles from "./AttachmentStrip.module.css";

const ACCEPTED =
  ".jpg,.jpeg,.png,.webp,.gif,.pdf,.txt,.csv,.json,.docx,.pptx,.xlsx";

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

  return (
    <div className={styles.strip}>
      <button
        type="button"
        className={styles.addBtn}
        aria-label="Attach files"
        onClick={() => fileInputRef.current?.click()}
      >
        <Icon />
      </button>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPTED}
        className={styles.hiddenInput}
        onChange={(e) => void handleFiles(e.target.files)}
      />

      {attachments.length > 0 && (
        <ul className={styles.list} aria-live="polite">
          {attachments.map((a) => (
            <li key={a.file_id} className={styles.item}>
              <span className={styles.fileName} title={a.original_filename}>
                {a.original_filename}
              </span>
              <span className={styles.fileSize}>{formatSize(a.size_bytes)}</span>
              <button
                type="button"
                className={styles.removeBtn}
                aria-label={`Remove ${a.original_filename}`}
                onClick={() => void handleRemove(a.file_id)}
              >
                &times;
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Icon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m21.4 11.6-8.9 8.9a5.3 5.3 0 0 1-7.5-7.5l9.2-9.2a3.6 3.6 0 0 1 5.1 5.1l-9.2 9.2a1.9 1.9 0 0 1-2.7-2.7l8.5-8.5" />
    </svg>
  );
}
