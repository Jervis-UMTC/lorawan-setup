FROM scratch

ARG SERVICE_NAME
ARG BINARY_SHA256
ARG SOURCE_DATE_EPOCH

LABEL org.opencontainers.image.title="${SERVICE_NAME}" \
      org.opencontainers.image.description="LoRaWAN security evidence service" \
      io.lorawan.evidence.binary.sha256="${BINARY_SHA256}" \
      io.lorawan.evidence.source-date-epoch="${SOURCE_DATE_EPOCH}"

COPY --chmod=0555 service /service

USER 65532:65532
EXPOSE 8080
STOPSIGNAL SIGTERM
ENTRYPOINT ["/service"]
