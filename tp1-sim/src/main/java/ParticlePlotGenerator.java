import java.io.*;
import java.util.ArrayList;
import java.util.List;



public class ParticlePlotGenerator {
    public static final String BIN_PATH = "/home/conradohillar/Documents/ITBA/4to_2C/SDS/tp1-bin/";
    private List<Particle> particles;
    private final long N;
    private final double L;

    public ParticlePlotGenerator(long N, double L, double minParticleRadius, double maxParticleRadius, boolean periodicBorders) {
        if (maxParticleRadius < minParticleRadius) {
            throw new IllegalArgumentException("maxParticleRadius must be larger or equal to minParticleRadius");
        }

        this.N = N;
        this.L = L;
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

                newParticle = new Particle(i, x_pos, y_pos,0,0, radius,0);
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


    public void exportFiles() {
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
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(BIN_PATH + "static.txt"))) {
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
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(BIN_PATH + "dynamic.txt"))) {
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