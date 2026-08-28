"use strict";

const required = [
    "NODE_RED_CREDENTIAL_SECRET",
    "NODE_RED_ADMIN_PASSWORD_HASH",
    "NODE_RED_MQTT_CLIENT_ID",
    "LORAWAN_REGION_ID",
    "TELEMETRY_DB_USER",
    "TELEMETRY_DB_PASSWORD",
];

for (const name of required) {
    const value = String(process.env[name] || "").trim();
    if (!value || value.startsWith("<")) {
        throw new Error(`Required Node-RED environment variable ${name} is missing or still a placeholder`);
    }
}

if (!/^[0-9a-f]{64}$/i.test(process.env.NODE_RED_CREDENTIAL_SECRET)) {
    throw new Error("NODE_RED_CREDENTIAL_SECRET must be exactly 64 hexadecimal characters");
}

if (!/^\$2[aby]\$/.test(process.env.NODE_RED_ADMIN_PASSWORD_HASH)) {
    throw new Error("NODE_RED_ADMIN_PASSWORD_HASH must be a bcrypt hash");
}

module.exports = {
    flowFile: "flows.json",
    credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET,
    uiPort: process.env.PORT || 1880,

    adminAuth: {
        type: "credentials",
        users: [{
            username: "admin",
            password: process.env.NODE_RED_ADMIN_PASSWORD_HASH,
            permissions: "*",
        }],
    },

    logging: {
        console: {
            level: "info",
            metrics: false,
            audit: false,
        },
    },
};
