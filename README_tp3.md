# TP3 – Simulación Dirigida por Eventos: Scanning Rate en Recinto Circular

**Sistema 1:** Partículas en movimiento rectilíneo uniforme dentro de un recinto circular
con un obstáculo fijo central. Colisiones elásticas entre pares, con el obstáculo y con la pared.

---

## Estructura del proyecto

```
tp3-sim/                     Motor de simulación (Java / Maven)
  src/main/java/
    EventDrivenMD.java        Simulación principal (event-driven MD)
    BenchmarkRunner.java      Runner para medir tiempo de cómputo vs N

tp3-vis/src/main/python/
    visualizer3.py            Animación interactiva (matplotlib)
    render_tp3_mp4.py         Exportación a MP4
    analysis_benchmark.py     Análisis 1.1 – Tiempo vs N
    analysis_scanning_rate.py Análisis 1.2 + 1.3 – Scanning rate y Fu(t)
    analysis_radial.py        Análisis 1.4 – Perfiles radiales

tp3-bin/                     Salidas generadas (frames, stats, metadata)
run_tp3.sh                   Script principal
```

---

## Parámetros físicos

| Variable       | Valor   | Descripción                              |
|---------------|---------|------------------------------------------|
| L             | 80 m    | Diámetro del recinto circular            |
| R_domain      | 40 m    | Radio del recinto                        |
| R_obstacle    | 1 m     | Radio del obstáculo central (fijo)       |
| R_particle    | 1 m     | Radio de las partículas móviles          |
| v₀            | 1 m/s   | Módulo de velocidad de las partículas    |
| m             | 1 kg    | Masa de las partículas                   |

**Estado de las partículas:**
- **Fresh** (verde, estado 0): estado inicial; la partícula aún no ha tocado el obstáculo.
- **Used** (violeta, estado 1): la partícula tocó el obstáculo central.
- Fresh → Used al colisionar con el obstáculo.
- Used → Fresh al colisionar con la pared exterior.

---

## Requisitos

- **Java 21+** con **Maven 3.x**
- **Python 3.10+** con:  `numpy`, `matplotlib`, `scipy`
- *(Opcional para MP4)* `ffmpeg` en el PATH

Instalar dependencias Python:
```bash
pip install numpy matplotlib scipy
```

---

## Uso rápido – animación

Editar los parámetros en las primeras líneas de `run_tp3.sh` y ejecutar:

```bash
./run_tp3.sh
```

Esto compila el simulador, corre una simulación y lanza la animación interactiva.

### Parámetros configurables en `run_tp3.sh`

| Variable      | Descripción                            | Default |
|--------------|----------------------------------------|---------|
| `N`           | Número de partículas                   | 100     |
| `SEED`        | Semilla aleatoria                      | 42      |
| `TF`          | Tiempo de simulación [s]               | 100.0   |
| `MAX_FRAMES`  | Máximo de frames a guardar (0=ninguno) | 2000    |
| `FRAME_EVERY` | Guardar frame cada N eventos           | 10      |
| `RENDER_MP4`  | Exportar a MP4 (true/false)            | false   |
| `FPS`         | Cuadros por segundo de la animación    | 30      |

---

## Uso avanzado – correr la simulación manualmente

```bash
cd tp3-sim

# Compilar
mvn package -DskipTests

# Correr con parámetros custom
mvn exec:java -Dexec.args="--n 200 --seed 7 --tf 300 --max-frames 3000 --frame-every 20 --bin ../tp3-bin"
```

### Flags del simulador

| Flag            | Tipo    | Descripción                                      | Default        |
|----------------|---------|--------------------------------------------------|----------------|
| `--n`           | int     | Número de partículas                             | 50             |
| `--seed`        | long    | Semilla aleatoria                                | 42             |
| `--tf`          | double  | Tiempo final de simulación [s]                   | 100.0          |
| `--max-frames`  | int     | Máximo de frames a escribir (0 = ninguno)        | 2000           |
| `--frame-every` | int     | Escribir frame cada N eventos                    | 10             |
| `--no-stats`    | flag    | No generar stats.txt (más rápido en benchmark)   | —              |
| `--bin`         | path    | Directorio de salida                             | `../tp3-bin`   |

---

## Formato de archivos de salida

### `tp3-bin/frames/frame_NNNNN.txt`
```
<tiempo>
<x>    <y>    <vx>    <vy>    <estado>
...                                      (N líneas, una por partícula)
```
Estado: `0` = fresh (verde), `1` = used (violeta).

### `tp3-bin/stats.txt`
```
time Cfc Nu
0.000000 0 0
...
```
- `Cfc`: número acumulado de transiciones fresh→used (contactos con el obstáculo).
- `Nu`: número de partículas usadas en ese instante.

### `tp3-bin/metadata.txt`
```
N 100
L 80.0
R_domain 40.0
R_obstacle 1.0
R_particle 1.0
v0 1.0
tf 100.0
seed 42
```

---

## Scripts de análisis

Todos los scripts de análisis corren las simulaciones necesarias internamente vía Maven.

### Análisis 1.1 – Tiempo de ejecución vs N

```bash
cd tp3-vis/src/main/python
python3 analysis_benchmark.py [--tf 5] [--runs 3] [--out benchmark.png]
```

Corre `BenchmarkRunner` (Java), parsea la salida y grafica `t_ejecucion(N)` con ajuste de ley de potencias.

### Análisis 1.2 + 1.3 – Scanning rate y Fu(t)

```bash
python3 analysis_scanning_rate.py [--tf 200] [--realizations 5] [--n-values 25 50 100 200]
```

Para cada N y cada realización:
1. Corre la simulación y lee `stats.txt`.
2. **1.2:** Ajusta linealmente `Cfc(t)` → pendiente J. Grafica `<J>(N)` con barras de error.
3. **1.3:** Calcula `Fu(t) = Nu(t)/N`, promedia las realizaciones. Grafica `<Fu>(t)` para cada N y reporta `t_ss` y `F_est`.

Genera: `tp3-bin/scanning_rate.png`, `tp3-bin/fu_evolution.png`.

### Análisis 1.4 – Perfiles radiales

```bash
python3 analysis_radial.py [--tf 200] [--realizations 3] [--frame-every 5]
```

Para cada N y realización, corre la simulación **con frames** y analiza cada frame:
- Filtra partículas frescas con `R_j · v_j < 0` (movimiento radial hacia el centro).
- Acumula densidad `<ρ_f^in>(S)` y velocidad radial `|<v_f^in>(S)|` en capas de ancho dS = 0.2 m.
- Calcula el flujo local `J_in(S) = <ρ_f^in>(S) × |<v_f^in>(S)|`.

Genera: `tp3-bin/radial_profile_N<N>.png` (uno por N) y `tp3-bin/radial_target_vs_N.png`.

---

## Física de las colisiones

El simulador usa una **cola de prioridad** de eventos (priority queue). Cada evento almacena
la predicción de cuándo dos cuerpos colisionarán y el conteo de colisiones de cada partícula
en el momento de la predicción (para invalidar eventos obsoletos).

**Tiempo de colisión entre partícula i y partícula j** (o partícula vs. obstáculo fijo):

$$t^* = \frac{-(\Delta\mathbf{r} \cdot \Delta\mathbf{v}) - \sqrt{(\Delta\mathbf{r} \cdot \Delta\mathbf{v})^2 - |\Delta\mathbf{v}|^2\,(|\Delta\mathbf{r}|^2 - \sigma^2)}}{|\Delta\mathbf{v}|^2}$$

**Tiempo de colisión con la pared exterior** (partícula dentro del círculo de radio R):

$$t^* = \frac{-(\mathbf{r} \cdot \mathbf{v}) + \sqrt{(\mathbf{r} \cdot \mathbf{v})^2 - |\mathbf{v}|^2\,(|\mathbf{r}|^2 - R_\text{eff}^2)}}{|\mathbf{v}|^2}$$

Las colisiones son elásticas: se intercambia la componente normal de la velocidad relativa
(partículas iguales) o se refleja la velocidad respecto a la normal (pared/obstáculo fijo).
