# migguard agent law

Before applying any SQLite or Prisma migrate against a file database:
1. Call the migguard MCP tool `check` with sql + db.
2. If the last line is not ALL_PASS or PRESERVED, stop. Do not apply.
3. INCOMPLETE means a RENAME without --table/--from-col/--to-col. Prove the values or stop.
4. APPLY_FAILED means block. Do not retry apply on the source file.
5. Never write the source --db. migguard clones.
6. If db_sha256 in the output does not match the file you were given, stop.
