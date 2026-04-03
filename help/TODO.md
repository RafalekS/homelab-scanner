# Homelab Scanner — TODO

## Status: Initial build — needs testing

---

## Pending

### Testing
- [ ] Test local collection (Pi5-NVMe)
- [ ] Test SSH to Pi4 (192.168.0.94)
- [ ] Test SSH to Pi5-AI (192.168.0.169)
- [ ] Test SSH to QNAP (192.168.0.166) — may need password in config
- [ ] Test SSH to ThinkPad Windows (192.168.0.106) — key auth now working
- [ ] Verify homelab-data.yaml output format
- [ ] Verify homelab-context.md output is correct

### Config
- [ ] Add QNAP password to config/config.json (currently blank)
- [ ] Confirm Pi4/Pi5-AI SSH key works from this machine

### Known gaps
- [ ] QNAP may not have `systemctl` — `services_check` not applicable, docker cmd may differ
- [ ] Windows docker command needs testing (may not be installed)

---

## Completed
- [x] SSH working from Pi5-NVMe to ThinkPad (key auth fixed — .ssh dir perms + SYSTEM ACL)
- [x] Project structure created
- [x] modules/ssh_client.py — paramiko with key→password fallback
- [x] modules/collectors.py — linux/windows/local/qnap collection
- [x] modules/data_store.py — YAML read/write
- [x] modules/context_builder.py — builds homelab-context.md from YAML
- [x] scanner.py — main entry, CLI flags, threaded scan
