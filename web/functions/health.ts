interface Env {
  BACKEND_URL: string;
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const backend = context.env.BACKEND_URL?.trim().replace(/\/$/, "");
  if (!backend) {
    return Response.json({ status: "error", detail: "BACKEND_URL not set" }, { status: 502 });
  }
  return fetch(`${backend}/health`);
};
