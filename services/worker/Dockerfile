FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /worker ./cmd/worker
FROM alpine:3.21
RUN adduser -D app
USER app
COPY --from=build /worker /worker
EXPOSE 8080
CMD ["/worker"]
