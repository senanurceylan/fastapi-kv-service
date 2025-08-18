from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Set, Optional

app = FastAPI(title="Remote Dictionary Service")

# In-memory store
lists: Dict[str, List[str]] = {}   # LPUSH/LPOP
sets_: Dict[str, Set[str]] = {}    # SADD/SPOP

class Command(BaseModel):
    command: str                 # "LPUSH" | "LPOP" | "SADD" | "SPOP"
    stack_name: str
    value: Optional[str] = None  # LPUSH/SADD için gerekli

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/command")
def run_command(cmd: Command):
    c = cmd.command.upper()

    if c == "LPUSH":
        if cmd.value is None:
            raise HTTPException(400, detail="LPUSH requires 'value'")
        lst = lists.setdefault(cmd.stack_name, [])
        lst.insert(0, cmd.value)  # başa ekle
        return {"ok": True, "type": "list", "name": cmd.stack_name, "length": len(lst)}

    elif c == "LPOP":
        lst = lists.get(cmd.stack_name, [])
        if not lst:
            return {"ok": True, "type": "list", "name": cmd.stack_name, "value": None}
        val = lst.pop(0)
        return {"ok": True, "type": "list", "name": cmd.stack_name, "value": val, "length": len(lst)}

    elif c in ("SADD", "SPUSH"):  # SPUSH'u uyumluluk için kabul ediyoruz
        if cmd.value is None:
            raise HTTPException(400, detail="SADD requires 'value'")
        s = sets_.setdefault(cmd.stack_name, set())
        before = len(s)
        s.add(cmd.value)
        return {"ok": True, "type": "set", "name": cmd.stack_name, "added": int(len(s) > before), "size": len(s)}

    elif c == "SPOP":
        s = sets_.get(cmd.stack_name, set())
        if not s:
            return {"ok": True, "type": "set", "name": cmd.stack_name, "value": None}
        val = s.pop()
        return {"ok": True, "type": "set", "name": cmd.stack_name, "value": val, "size": len(s)}

    else:
        raise HTTPException(400, detail=f"Unknown command: {cmd.command}")
