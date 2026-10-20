FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn -B dependency:go-offline
COPY src ./src
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21-jre-jammy
WORKDIR /app
RUN groupadd --system equifolio && useradd --system --gid equifolio equifolio
COPY --from=build /app/target/equifolio-backend-1.0.0-SNAPSHOT.jar /app/backend.jar
USER equifolio
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/backend.jar"]
