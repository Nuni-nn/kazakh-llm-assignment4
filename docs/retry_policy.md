# Frozen Retry Policy

- Three planned generation runs are executed for each prompt-model pair.
- A request may be retried at most two times after the initial attempt.
- Retries are allowed only for transport errors, timeouts, rate-limit responses, or provider-side 5xx/server failures.
- A valid response is never regenerated because it contains linguistic errors, fails a prompt constraint, is unusually short/long, or is otherwise unfavourable.
- Every attempt is logged with run ID, attempt number, timestamp, provider request ID when available, status, and error message.
- If all permitted retries fail, the planned run remains in the dataset with status FAILED.
