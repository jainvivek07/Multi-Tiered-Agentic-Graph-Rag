import React from 'react';
import { useChatStore } from '../../store/chatStore';
import type { PipelineStep } from '../../types/api';
import styles from './PipelineHUD.module.css';

const STEPS: { key: PipelineStep; label: string; color: string }[] = [
  { key: 'cache_check',    label: 'Cache',       color: 'emerald' },
  { key: 'input_guard',    label: 'Guard',       color: 'amber'   },
  { key: 'router',         label: 'Router',      color: 'cyan'    },
  { key: 'vector_search',  label: 'Vector',      color: 'cyan'    },
  { key: 'cypher_search',  label: 'Graph',       color: 'violet'  },
  { key: 'output_guard',   label: 'Verify',      color: 'amber'   },
  { key: 'synthesizer',    label: 'Synthesize',  color: 'cyan'    },
];

export function PipelineHUD() {
  const streamingStatus = useChatStore((s) => s.streamingStatus);
  const pipeline = useChatStore((s) => s.pipeline);
  const isVisible = streamingStatus === 'streaming';

  if (!isVisible) return null;

  return (
    <div className={styles.hud} role="status" aria-live="polite">
      {STEPS.map((step, i) => {
        const isCompleted = pipeline.completedSteps.includes(step.key);
        const isActive = pipeline.activeStep === step.key;

        return (
          <React.Fragment key={step.key}>
            <div
              className={[
                styles.step,
                styles[step.color],
                isActive ? styles.active : '',
                isCompleted ? styles.completed : '',
              ].join(' ')}
              title={step.label}
            >
              <span className={styles.dot} />
              <span className={styles.label}>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={[styles.connector, isCompleted ? styles.connectorDone : ''].join(' ')} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
