-- Prisma docs "customizing migrations" BAD form:
-- they generate DROP + ADD instead of RENAME, which deletes data.
-- https://www.prisma.io/docs/orm/prisma-migrate/workflows/customizing-migrations
ALTER TABLE "Profile" DROP COLUMN "biograpy";
ALTER TABLE "Profile" ADD COLUMN "biography" TEXT NOT NULL;
