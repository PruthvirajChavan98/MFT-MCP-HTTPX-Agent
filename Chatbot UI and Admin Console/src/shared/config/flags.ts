// Feature flags are resolved at runtime from RUNTIME_CONFIG (docker-entrypoint-runtime-config.sh).
// Dead flag constants (adminEnterpriseRedesign, adminKnowledgeBaseEnterprise) were removed
// when the legacy UI variants were deleted and enterprise became the canonical implementation.
export const flags = {} as const
