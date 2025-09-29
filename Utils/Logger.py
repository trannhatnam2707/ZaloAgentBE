class AgentLogger:
    def __init__(self):
        self.logs = []
    
    def log(self, step: str, detail: str):
        entry = {"step": step, "detail": detail}
        self.logs.append(entry)
        print(f"[{step}] {detail}")

    def get_logs(self):
        return self.logs        