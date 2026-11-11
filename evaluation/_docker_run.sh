#!/bin/sh
# Menjalankan runner evaluasi di dalam container (FAISS diblokir Application Control di host Windows ini).
# Kode sistem di-mount dari host, jadi perubahan kode langsung terpakai.
# Image 'helpdesk-eval' dibangun dari wheel offline (lihat README bagian "Cara mereproduksi").
# Pemakaian: MSYS_NO_PATHCONV=1 sh evaluation/_docker_run.sh evaluation/run_evaluation.py --suite scenarios --tag after
docker run --rm --env-file system/.env -v "$(pwd -W 2>/dev/null || pwd)":/repo -w /repo helpdesk-eval python "$@"
