import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;



public class ParticlePlotGenerator {
    /**
     * Default output directory for TP1 artifacts (static/dynamic/neighbors/bench).
     * Resolved relative to current working directory, so it works across machines.
     */
    public static final Path DEFAULT_BIN_DIR = resolveDefaultBinDir();

    private List<Particle> particles;
    private final long N;
    private final double L;
    private final Path binDir;

    public ParticlePlotGenerator(long N, double L, double minParticleRadius, double maxParticleRadius,
                                 boolean periodicBorders, double velocityModule) {
        this(N, L, minParticleRadius, maxParticleRadius, periodicBorders, velocityModule, DEFAULT_BIN_DIR);
    }

    public ParticlePlotGenerator(long N, double L, double minParticleRadius, double maxParticleRadius,
                                 boolean periodicBorders, double velocityModule, Path binDir) {
        if (maxParticleRadius < minParticleRadius) {
            throw new IllegalArgumentException("maxParticleRadius must be larger or equal to minParticleRadius");
        }

        this.N = N;
        this.L = L;
        this.binDir = binDir.toAbsolutePath().normalize();
        particles = new ArrayList<>((int) N);

        for (int i = 0; i < N; i++) {
            Particle newParticle;
            int attempts = 0;
            int maxAttempts = 10000;

            do {
                double radius = Math.random() * (maxParticleRadius - minParticleRadius) + minParticleRadius;
                double minPos = periodicBorders ? 0 :radius;
                double maxPos = periodicBorders ? L : L - radius;
                double x_pos = Math.random() * (maxPos - minPos) + minPos;
                double y_pos = Math.random() * (maxPos - minPos) + minPos;
                double angle = Math.random() * 2 * Math.PI;
                double vx = velocityModule * Math.cos(angle);
                double vy = velocityModule * Math.sin(angle);

                newParticle = new Particle(i, x_pos, y_pos, vx, vy, radius,0);
                attempts++;

                if (attempts >= maxAttempts) {
                    throw new RuntimeException(
                            "Could not place particle " + i + " without overlap after " + maxAttempts + " attempts. " +
                                    "Try increasing L or reducing N/maxParticleRadius."
                    );
                }
            } while (overlapsWithAny(newParticle));

            particles.add(newParticle);
        }
    }

    private static Path resolveDefaultBinDir() {
        String fromEnv = System.getenv("TP1_BIN_PATH");
        if (fromEnv != null && !fromEnv.isEmpty()) {
            return Paths.get(fromEnv).toAbsolutePath().normalize();
        }
        // IntelliJ typically sets working dir to module root; CLI often uses repo root.
        Path cwd = Paths.get(System.getProperty("user.dir")).toAbsolutePath().normalize();
        Path candidateInCwd = cwd.resolve("tp1-bin");
        if (Files.isDirectory(candidateInCwd)) {
            return candidateInCwd;
        }
        return cwd.resolve("../tp1-bin").normalize();
    }

    public Path binFile(String filename) {
        return binDir.resolve(filename);
    }

    public void exportFiles() {
        try {
            Files.createDirectories(binDir);
        } catch (IOException e) {
            throw new RuntimeException("Failed to create output directory: " + binDir, e);
        }
        exportStatic();
        exportDynamic();
    }

    private boolean overlapsWithAny(Particle candidate) {
        for (Particle existing : particles) {
            if(candidate.overlaps(existing)){
                return true;
            }
        }
        return false;
    }

    private void exportStatic() {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(binFile("static.txt").toString()))) {
            writer.write(String.format("%d", N));
            writer.newLine();
            writer.write(String.format("%.5f", L));
            writer.newLine();
            for (Particle particle : particles) {
                writer.write(String.format("%.6f", particle.radius()));
                writer.newLine();
            }
        } catch (IOException e) {
            throw new RuntimeException("Failed to export static.txt", e);
        }
    }

    private void exportDynamic() {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(binFile("dynamic.txt").toString()))) {
            writer.write(String.format("%.6f", 0.0));
            writer.newLine();
            for (Particle particle : particles) {
                writer.write(String.format("%.6f\t%.6f\t%.6f\t%.6f", particle.x(), particle.y(), particle.vx(), particle.vy()));
                writer.newLine();
            }
        } catch (IOException e) {
            throw new RuntimeException("Failed to export dynamic.txt", e);
        }
    }
}
