# Java Monolith — Multi-stage Docker build
#
# Stage 1: Build the JAR with Maven
# Stage 2: Run with a minimal JRE image
#
# NOTE: First build requires Maven Central access to download dependencies.
# Subsequent builds use the Docker layer cache for the .m2 directory.

# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM maven:3.9-eclipse-temurin-17 AS build

WORKDIR /workspace

# Copy POM first for layer caching — only re-downloads deps when pom.xml changes
COPY pom.xml .
RUN mvn dependency:go-offline -q

# Copy source and build
COPY src/ ./src/
RUN mvn package -DskipTests -q

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

COPY --from=build /workspace/target/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-Dspring.profiles.active=prod", "-jar", "/app/app.jar"]
