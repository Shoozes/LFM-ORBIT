export const IS_HOSTED_BUILD = import.meta.env.MODE === "hosted" || import.meta.env.VITE_ORBIT_BUILD === "hosted";
export const HOSTED_ROUTE = IS_HOSTED_BUILD ? "/" : "/hosted";
