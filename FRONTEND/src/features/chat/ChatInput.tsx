import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send } from 'lucide-react';
import { useChatStore } from '../../store/chatStore';
import { sessionApi } from '../../api/chatApi';
import styles from './ChatInput.module.css';

interface ChatInputProps {
  onSend: (message: string, category: string) => void;
}

export function ChatInput({ onSend }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [categories, setCategories] = useState<string[]>([]);
  const [category, setCategory] = useState<string>('');
  const [loadingCats, setLoadingCats] = useState(true);
  
  const streamingStatus = useChatStore((s) => s.streamingStatus);
  const isStreaming = streamingStatus === 'streaming';
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let mounted = true;
    sessionApi.getCategories().then(cats => {
      if (!mounted) return;
      setCategories(cats);
      // No default category selected - user must choose
      setLoadingCats(false);
    }).catch(err => {
      console.error(err);
      if (!mounted) return;
      setCategories([]);
      setLoadingCats(false);
    });
    return () => { mounted = false; };
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [message]);

  const handleSend = useCallback(() => {
    const trimmed = message.trim();
    if (!trimmed || isStreaming || !category) return;
    onSend(trimmed, category);
    setMessage('');
  }, [message, category, isStreaming, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasCategories = categories.length > 0;
  const disableInput = isStreaming || !hasCategories || loadingCats;
  const canSend = message.trim().length > 0 && !disableInput && Boolean(category);

  let placeholderText = "Ask anything… (Shift+Enter for new line)";
  if (loadingCats) {
    placeholderText = "Loading categories...";
  } else if (!hasCategories) {
    placeholderText = "No documents ingested";
  } else if (!category) {
    placeholderText = "Select a category above to ask a question...";
  } else {
    placeholderText = `Ask anything about ${category}… (Shift+Enter for new line)`;
  }

  return (
    <div className={styles.container}>
      {/* Topics */}
      <div className={styles.topicRow}>
        <span className={styles.topicLabel}>Topic:</span>
        {loadingCats ? (
          <span className={styles.topicPill}>Loading...</span>
        ) : hasCategories ? (
          <select
            className={styles.topicSelect}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            disabled={isStreaming}
            aria-label="Select topic"
          >
            <option value="" disabled>Select a category...</option>
            {categories.map(c => (
              <option key={c} value={c}>
                {c.charAt(0).toUpperCase() + c.slice(1)}
              </option>
            ))}
          </select>
        ) : (
          <span className={styles.noTopics}>No documents ingested</span>
        )}
      </div>

      <div className={styles.inputRow}>
        {/* Text area */}
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholderText}
          className={styles.textarea}
          rows={1}
          disabled={disableInput}
          aria-label="Chat message"
          aria-multiline="true"
        />

        {/* Send button */}
        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          className={styles.sendBtn}
          aria-label="Send message"
          title={
            !hasCategories
              ? "No documents ingested"
              : !category
              ? "Please select a category above"
              : !message.trim()
              ? "Enter a message"
              : "Send message"
          }
        >
          {isStreaming ? (
            <span className={styles.spinner} aria-hidden />
          ) : (
            <Send size={16} />
          )}
        </button>
      </div>
    </div>
  );
}
