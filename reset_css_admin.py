import json

with open("data/users.json","r",encoding="utf-8") as f:
    users=json.load(f)

u=users["00000"]

u["password_hash"]="22b72c5454bbf0a04b931b214b83ac943e47f8ffc1e51b1d68351d79e99afb20"
u["failed_attempts"]=0
u["locked"]=False
u["locked_at"]=None
u["lockout_until"]=None
u["lockout_seconds"]=0
u["lockout_started_at"]=None

with open("data/users.json","w",encoding="utf-8") as f:
    json.dump(users,f,indent=2)

print("RESET COMPLETE")
