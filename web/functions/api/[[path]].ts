interface Env {
  BACKEND_URL: string;
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const backend = context.env.BACKEND_URL?.trim().replace(/\/$/, "");
  if (!backend) {
    return Response.json(
      { detail: "请在 Cloudflare Pages 环境变量中配置 BACKEND_URL（后端 API 根地址，如 https://api.example.com）" },
      { status: 502 },
    );
  }

  const incoming = new URL(context.request.url);
  const targetUrl = `${backend}${incoming.pathname}${incoming.search}`;

  const headers = new Headers(context.request.headers);
  headers.delete("host");

  const init: RequestInit = {
    method: context.request.method,
    headers,
    redirect: "manual",
  };
  if (context.request.method !== "GET" && context.request.method !== "HEAD") {
    init.body = await context.request.arrayBuffer();
  }

  return fetch(targetUrl, init);
};
