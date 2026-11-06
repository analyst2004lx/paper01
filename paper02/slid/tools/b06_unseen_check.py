from algorithm import ingest
from tools.baseline_diag import split

raw = ingest.read_xes(ingest.default_log_path())
live = ingest.valid(raw, drop_failure=True)
train, calib, test = split(live)
tr = {(a.device, a.op) for a in train}
trc = tr | {(a.device, a.op) for a in calib}
print("unseen vs train:", sum((a.device, a.op) not in tr for a in test), "/", len(test))
print("unseen vs train+calib:", sum((a.device, a.op) not in trc for a in test), "/", len(test))
