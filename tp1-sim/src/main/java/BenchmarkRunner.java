import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public class BenchmarkRunner {

    // Densidad objetivo rho = N0 / L0^2 con N0 = 250, L0 = 20
    private static final double REFERENCE_L = 20.0;
    private static final long REFERENCE_N = 100;
    private static final double TARGET_DENSITY = REFERENCE_N / (REFERENCE_L * REFERENCE_L);

    private static final double RC = 1.0;
    private static final double MIN_RADIUS = 0.23;
    private static final double MAX_RADIUS = 0.26;
    private static final boolean PERIODIC_BORDERS = false;

    // Solo variamos N; la densidad fija define L(N). M se calcula internamente en el CIM.
    private static final long[] NS = {10, 50, 100, 500, 1000, 2000};
    private static final int WARMUP_RUNS = 20;
    private static final int MEASURED_RUNS = 100;

    public static void main(String[] args) throws IOException {
        long start = System.nanoTime();
        Path binDir = ParticlePlotGenerator.DEFAULT_BIN_DIR;
        Files.createDirectories(binDir);
        String csvPath = binDir.resolve("benchmark_results.csv").toString();

        try (BufferedWriter writer = new BufferedWriter(new FileWriter(csvPath))) {
            writer.write("N,method,run_index,time_ns");
            writer.newLine();

            // Warmup global para que la JVM compile los hot paths
            for (int i = 0; i < WARMUP_RUNS; i++) {
                for (long N : NS) {
                    double L = Math.sqrt(N / TARGET_DENSITY);
                    ParticlePlotGenerator generator = new ParticlePlotGenerator(N, L, MIN_RADIUS, MAX_RADIUS,
                            PERIODIC_BORDERS,0);
                    generator.exportFiles();

                    String staticPath = generator.binFile("static.txt").toString();
                    String dynamicPath = generator.binFile("dynamic.txt").toString();
                    StaticData sd = InputParser.parseStatic(staticPath);
                    DynamicData dd = InputParser.parseDynamic(dynamicPath);
                    List<Particle> particles = InputParser.buildParticles(sd, dd);

                    CellIndexMethodNeighborFinder cimCellIndex = new CellIndexMethodNeighborFinder(N, L, RC,
                            PERIODIC_BORDERS, particles);
                    cimCellIndex.findNeighbors();

                    CellIndexMethodNeighborFinder cimBruteForce = new CellIndexMethodNeighborFinder(N, L, RC,
                            PERIODIC_BORDERS, particles);
                    cimBruteForce.findNeighborsBruteForce();
                }
            }

            // Corridas medidas que se vuelcan al CSV
            for (int runIndex = 0; runIndex < MEASURED_RUNS; runIndex++) {
                for (long N : NS) {
                    double L = Math.sqrt(N / TARGET_DENSITY);
                    ParticlePlotGenerator generator = new ParticlePlotGenerator(N, L, MIN_RADIUS, MAX_RADIUS,
                            PERIODIC_BORDERS,0);
                    generator.exportFiles();

                    String staticPath = generator.binFile("static.txt").toString();
                    String dynamicPath = generator.binFile("dynamic.txt").toString();
                    StaticData sd = InputParser.parseStatic(staticPath);
                    DynamicData dd = InputParser.parseDynamic(dynamicPath);
                    List<Particle> particles = InputParser.buildParticles(sd, dd);

                    // Cell Index Method
                    CellIndexMethodNeighborFinder cimCellIndex = new CellIndexMethodNeighborFinder(N, L, RC,
                            PERIODIC_BORDERS, particles);
                    long t0 = System.nanoTime();
                    cimCellIndex.findNeighbors();
                    long t1 = System.nanoTime();
                    long cellIndexTime = t1 - t0;
                    writeResult(writer, N, "cell_index", runIndex, cellIndexTime);

                    // Brute force
                    CellIndexMethodNeighborFinder cimBruteForce = new CellIndexMethodNeighborFinder(N, L, RC,
                            PERIODIC_BORDERS, particles);
                    long t2 = System.nanoTime();
                    cimBruteForce.findNeighborsBruteForce();
                    long t3 = System.nanoTime();
                    long bruteForceTime = t3 - t2;
                    writeResult(writer, N, "brute_force", runIndex, bruteForceTime);
                }
            }
        }
        long end = System.nanoTime();
        System.out.printf("Total benchmark time: %.3f s", (end - start)/1000000000.0);
    }

    private static void writeResult(BufferedWriter writer, long N, String method, int runIndex, long timeNs)
            throws IOException {
        writer.write(String.format("%d,%s,%d,%d", N, method, runIndex, timeNs));
        writer.newLine();
        writer.flush();
    }
}
