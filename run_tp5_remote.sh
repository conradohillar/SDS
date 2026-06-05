#!/usr/bin/env bash
# TP5 Sistema 3 – orquestador local que corre todo en macmini via SSH.
#
# Flujo:
#   1. (opcional) git push de los cambios locales
#   2. git pull en el remoto
#   3. (opcional) build con maven en el remoto
#   4. (opcional) limpieza de runs viejos
#   5. ActiveRunner con la grilla configurada
#   6. analysis_pressure_vel.py + analysis_jamming.py
#   7. rsync de las imagenes generadas a local
#
# Todos los parametros son configurables via variables de entorno o editando
# este script. Ejemplos:
#
#   ./run_tp5_remote.sh                             # corrida default
#   RUNS=2 TF=2000 ./run_tp5_remote.sh              # corrida rapida
#   N_VALUES="15,18,21,24,27,30" V0=1.2 ./run_tp5_remote.sh
#   DO_PUSH=0 CLEAN_RUNS=0 ./run_tp5_remote.sh      # re-plot sobre runs existentes
#
set -euo pipefail

# ─── Remote host ─────────────────────────────────────────────────────────────
REMOTE_HOST="${REMOTE_HOST:-macmini}"
REMOTE_REPO="${REMOTE_REPO:-/Users/conradohillar/Documents/ITBA/4to_2c/SDS}"
REMOTE_MVN="${REMOTE_MVN:-/opt/homebrew/bin/mvn}"
REMOTE_PYTHON="${REMOTE_PYTHON:-/usr/bin/python3}"

# ─── Parametros fisicos (TimeDrivenActive) ───────────────────────────────────
R_P="${R_P:-1.6}"           # radio de particula [cm]
R_DOMAIN="${R_DOMAIN:-10.0}" # radio del recinto [cm]
V0="${V0:-0.825}"           # velocidad propulsion [cm/s]
KAPPA="${KAPPA:-50.0}"      # constante elastica de contacto
SIGMA_ETA="${SIGMA_ETA:-0.0825}" # desviacion ruido angular

# ─── Parametros de simulacion (grilla) ───────────────────────────────────────
N_VALUES="${N_VALUES:-20,21,22,23,24,25,26,27}"   # lista CSV de N
MODES="${MODES:-quiral,random}"                   # subset de {quiral,random}
RUNS="${RUNS:-50}"                                # realizaciones por (mode,N)
TF="${TF:-10000.0}"                               # tiempo final [s]
DT="${DT:-0.01}"                                  # paso RK4 [s]
DT2="${DT2:-0.1}"                                 # intervalo de output [s]
NO_FRAMES="${NO_FRAMES:-1}"                       # 1 → --no-frames

# ─── Parametros de analisis ──────────────────────────────────────────────────
JAM_THRESHOLD="${JAM_THRESHOLD:-0.1}"  # fraccion de v0
STAT_FRAC="${STAT_FRAC:-0.5}"          # cola para estadisticas estacionarias

# ─── Flags de workflow ───────────────────────────────────────────────────────
DO_PUSH="${DO_PUSH:-1}"        # push local antes de pull remoto
DO_BUILD="${DO_BUILD:-1}"      # mvn package en remoto
CLEAN_RUNS="${CLEAN_RUNS:-1}"  # rm -rf runs/ viejos antes de simular
DO_SIM="${DO_SIM:-1}"          # 0 → saltar simulacion (solo re-plot)
DO_ANALYSIS="${DO_ANALYSIS:-1}"
SYNC_PLOTS="${SYNC_PLOTS:-1}"

# ─── Rutas locales ───────────────────────────────────────────────────────────
LOCAL_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_PLOTS_DIR="${LOCAL_PLOTS_DIR:-$LOCAL_REPO/tp5-bin/images}"
REMOTE_BIN="$REMOTE_REPO/tp5-bin"

# normaliza listas CSV quitando espacios para que el shell no las parta
N_VALUES="${N_VALUES// /}"
MODES="${MODES// /}"

NO_FRAMES_FLAG=""
[[ "$NO_FRAMES" == "1" ]] && NO_FRAMES_FLAG="--no-frames"

EXEC_ARGS="--tf $TF --dt $DT --dt2 $DT2 --runs $RUNS \
--n-values $N_VALUES --modes $MODES \
--r-p $R_P --r-domain $R_DOMAIN --v0 $V0 --kappa $KAPPA --sigma-eta $SIGMA_ETA \
--bin $REMOTE_BIN $NO_FRAMES_FLAG"

cat <<EOF
═══ TP5 remote runner ═══
  remote   : $REMOTE_HOST:$REMOTE_REPO
  fisica   : r_p=$R_P  R=$R_DOMAIN  v0=$V0  kappa=$KAPPA  sigma_eta=$SIGMA_ETA
  grilla   : N=$N_VALUES  modes=$MODES  runs=$RUNS  tf=$TF  dt=$DT  dt2=$DT2
  flags    : NO_FRAMES=$NO_FRAMES  CLEAN_RUNS=$CLEAN_RUNS  DO_PUSH=$DO_PUSH  DO_BUILD=$DO_BUILD
  analisis : JAM_THRESHOLD=$JAM_THRESHOLD  STAT_FRAC=$STAT_FRAC
EOF
echo ""

# ─── 1. Push local ───────────────────────────────────────────────────────────
if [[ "$DO_PUSH" == "1" ]]; then
    echo "▶ Pushing local commits ..."
    git -C "$LOCAL_REPO" push
fi

# ─── 2. Pull remoto ──────────────────────────────────────────────────────────
echo "▶ git pull en $REMOTE_HOST ..."
ssh "$REMOTE_HOST" "cd '$REMOTE_REPO' && git pull"

# ─── 3. Build remoto ─────────────────────────────────────────────────────────
if [[ "$DO_BUILD" == "1" ]]; then
    echo "▶ mvn package en $REMOTE_HOST ..."
    ssh "$REMOTE_HOST" "cd '$REMOTE_REPO/tp5-sim' && '$REMOTE_MVN' -q package -DskipTests"
fi

# ─── 4. Limpieza ─────────────────────────────────────────────────────────────
if [[ "$CLEAN_RUNS" == "1" && "$DO_SIM" == "1" ]]; then
    echo "▶ Borrando runs viejos en $REMOTE_BIN ..."
    ssh "$REMOTE_HOST" "rm -rf '$REMOTE_BIN/runs' '$REMOTE_BIN/active_runner.log'"
fi

# ─── 5. Simulacion ───────────────────────────────────────────────────────────
if [[ "$DO_SIM" == "1" ]]; then
    echo "▶ ActiveRunner en $REMOTE_HOST ..."
    echo "   args: $EXEC_ARGS"
    ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_BIN' && cd '$REMOTE_REPO/tp5-sim' && \
        '$REMOTE_MVN' -q exec:java \
        -Dexec.mainClass=ActiveRunner \
        '-Dexec.args=$EXEC_ARGS' 2>&1 | tee '$REMOTE_BIN/active_runner.log'"
fi

# ─── 6. Analisis ─────────────────────────────────────────────────────────────
if [[ "$DO_ANALYSIS" == "1" ]]; then
    echo "▶ Generando plots en $REMOTE_HOST ..."
    ssh "$REMOTE_HOST" "cd '$REMOTE_REPO/tp5-vis/src/main/python' && \
        '$REMOTE_PYTHON' analysis_pressure_vel.py --bin-dir '$REMOTE_BIN' --n-runs $RUNS --stat-frac $STAT_FRAC && \
        '$REMOTE_PYTHON' analysis_jamming.py      --bin-dir '$REMOTE_BIN' --n-runs $RUNS --threshold $JAM_THRESHOLD --stat-frac $STAT_FRAC"
fi

# ─── 7. Sync plots ───────────────────────────────────────────────────────────
if [[ "$SYNC_PLOTS" == "1" ]]; then
    echo "▶ Sincronizando plots → $LOCAL_PLOTS_DIR ..."
    mkdir -p "$LOCAL_PLOTS_DIR"
    rsync -av --delete "$REMOTE_HOST:$REMOTE_BIN/images/" "$LOCAL_PLOTS_DIR/"
fi

echo ""
echo "✔ Listo. Plots en: $LOCAL_PLOTS_DIR"
