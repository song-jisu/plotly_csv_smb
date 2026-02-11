from nas_smb.nas_smb import NasSMB

# NAS_IP/NAS_USER/NAS_PASSWORD/NAS_SHARE are loaded from .env via NasSMB()
nas = NasSMB()

for p in ["data/", "data/경북대IT1호2층/", "data/경북대IT1호2층/LOG_SMARTCARE/"]:
    try:
        files = nas.list_files(p)
        print(f"\n[{p}] count={len(files)}")
        for f in files[:10]:
            print(" ", f)
    except Exception as e:
        print(f"\n[{p}] ERROR: {e}")
