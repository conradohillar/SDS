import java.util.Objects;

import static java.lang.Math.pow;
import static java.lang.Math.sqrt;

public record Particle(double x, double y, double radius) {
    public double distanceTo(Particle p) {
        double dx =  x - p.x - radius - p.radius;
        double dy = y - p.y - radius - p.radius;
        return sqrt(dx*dx + dy*dy);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Particle particle = (Particle) o;
        return (particle.x() == x) && (particle.y() == y) && (particle.radius == radius);
    }

    @Override
    public int hashCode() {
        return Objects.hash(x, y, radius);
    }
}
