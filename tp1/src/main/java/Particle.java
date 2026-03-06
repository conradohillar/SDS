import java.util.Objects;

import static java.lang.Math.pow;
import static java.lang.Math.sqrt;

public record Particle(double x, double y, double radius) {
    public double distanceTo(Particle p) {
        double distanceX =  x - p.x - radius - p.radius;
        double distanceY = y - p.y - radius - p.radius;
        return sqrt(pow(distanceX, 2) + pow(distanceY, 2));
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
