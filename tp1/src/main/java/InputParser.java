import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

public class InputParser {
    public static StaticData parseStatic(String path) throws IOException {
        try (BufferedReader br = new BufferedReader(new FileReader(path))) {
            long   N = Long.parseLong(br.readLine().trim());
            double L = Double.parseDouble(br.readLine().trim());

            List<double[]> radiiAndProps = new ArrayList<>();
            String line;
            while ((line = br.readLine()) != null && !line.isBlank()) {
                String[] parts = line.trim().split("\\s+");
                double radius   = Double.parseDouble(parts[0]);
                double property = Double.parseDouble(parts[1]);
                radiiAndProps.add(new double[]{radius, property});
            }
            return new StaticData(N, L, radiiAndProps);
        }
    }

    public static DynamicData parseDynamic(String path) throws IOException {
        try (BufferedReader br = new BufferedReader(new FileReader(path))) {
            double t = Double.parseDouble(br.readLine().trim()); // t0, unused

            List<double[]> positions = new ArrayList<>();
            String line;
            while ((line = br.readLine()) != null && !line.isBlank()) {
                String[] parts = line.trim().split("\\s+");
                double x  = Double.parseDouble(parts[0]);
                double y  = Double.parseDouble(parts[1]);
                double vx = Double.parseDouble(parts[2]);
                double vy = Double.parseDouble(parts[3]);
                positions.add(new double[]{x, y, vx, vy});
            }
            return new DynamicData(t, positions);
        }
    }

    public static List<Particle> buildParticles(StaticData sd, DynamicData dd) {
        List<Particle> particles = new ArrayList<>();
        for (int i = 0; i < sd.N(); i++) {
            int    id       = i + 1;
            double radius   = sd.radiiAndProps().get(i)[0];
            double property = sd.radiiAndProps().get(i)[1];
            double x        = dd.positions().get(i)[0];
            double y        = dd.positions().get(i)[1];
            double vx       = dd.positions().get(i)[2];
            double vy       = dd.positions().get(i)[3];
            particles.add(new Particle(id, x, y, vx, vy, radius, property));
        }
        return particles;
    }
}