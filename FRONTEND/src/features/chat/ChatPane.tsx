import { useEffect, useRef } from 'react';
import { useChatStore } from '../../store/chatStore';
import { useChat } from '../../hooks/useChat';
import { MessageBubble } from './MessageBubble';
import { PipelineHUD } from './PipelineHUD';
import { ChatInput } from './ChatInput';
import styles from './ChatPane.module.css';

interface ChatPaneProps {
  sessionId: string;
}

export function ChatPane({ sessionId }: ChatPaneProps) {
  const messages = useChatStore((s) => s.messages[sessionId]) ?? [];
  const { sendMessage } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages/tokens
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (message: string, category: string) => {
    sendMessage(message, category, sessionId);
  };

  return (
    <div className={styles.pane}>
      {/* Messages */}
      <div className={styles.messages} role="log" aria-label="Conversation">
        {messages.length === 0 && (
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>Intelligence Studio</p>
            <p className={styles.emptySubtitle}>
              Ask anything. Your query traverses the knowledge graph and semantic search space.
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Pipeline progress strip */}
      <PipelineHUD />

      {/* Input */}
      <ChatInput onSend={handleSend} />
    </div>
  );
}
