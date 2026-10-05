/* Which deployment this bundle was built for, and the one place that decides.

   IT COMES FROM THE EXISTING `ENV`, NOT A NEW VARIABLE. deploy/.env already
   carries ENV=development or ENV=production. It is shipped empty on purpose
   because there is no safe default, and checks/preflight-env.sh refuses
   anything but those two values, so it is a required and validated choice on
   every box already. deploy/docker-compose.prod.yml hands it to the web image
   as a build arg, which means one setting per box rather than two that can
   drift apart.

   BAKED IN AT BUILD TIME, like every other VITE_ value here. The web container
   is nginx serving static files and has no process that reads an environment,
   so this is substituted into the bundle by `vite build`. Changing it needs a
   rebuild, not a restart. See web/Dockerfile.

   UNSET MEANS NON-PRODUCTION, AND THAT DIRECTION IS THE WHOLE POINT. A
   production site wrongly wearing a development banner is embarrassing,
   obvious within seconds and fixed in minutes. A development site silently
   looking like production is the failure this exists to prevent: somebody
   reports a bug that was fixed on the other box, or a real creator signs up
   somewhere their account does not exist. Of the two ways to be wrong, only
   one of them is quiet, so the default is the loud one. */

/* Split out from the constant below because this is the decision worth
   testing and import.meta.env is fixed at module load, so a test cannot vary
   it. Trimmed and lowercased rather than compared raw: the value arrives
   through a shell, a compose file and a Dockerfile, and any of the three can
   add a space. */
export function isProductionBuild(raw: string | undefined): boolean {
  return (raw ?? "").trim().toLowerCase() === "production";
}

export const IS_PRODUCTION: boolean = isProductionBuild(import.meta.env.VITE_KOLABO_ENV);
