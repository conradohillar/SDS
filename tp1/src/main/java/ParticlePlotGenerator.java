import java.io.*;
import java.util.ArrayList;
import java.util.List;

public class ParticlePlotGenerator {
    List<Particle> particles;

    public ParticlePlotGenerator(long N, double L, double rc, double minParticleRadius, double maxParticleRadius) {
        if (maxParticleRadius < minParticleRadius) {
            throw new IllegalArgumentException("maxParticleRadius must be larger or equal to minParticleRadius");
        }

        particles = new ArrayList<>();

        for (int i = 0; i < N; i++) {
            Particle newParticle;
            int attempts = 0;
            int maxAttempts = 10000;

            do {
                double x_pos = Math.random() * L;
                double y_pos = Math.random() * L;
                double radius = Math.random() * (maxParticleRadius - minParticleRadius) + minParticleRadius;
                newParticle = new Particle(i, x_pos, y_pos, radius);
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
        try (BufferedWriter writer = new BufferedWriter(new FileWriter("static.txt"))) {
            for (Particle particle : particles) {
                writer.write(String.valueOf(particle.radius()));
                writer.newLine();
            }
        } catch (IOException e) {
            throw new RuntimeException("Failed to export static.txt", e);
        }
    }

    private void exportDynamic() {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter("dynamic.txt"))) {
            for (Particle particle : particles) {
                writer.write((particle.x()) + "\t" + particle.y());
                writer.newLine();
            }
        } catch (IOException e) {
            throw new RuntimeException("Failed to export static.txt", e);
        }
    }
}