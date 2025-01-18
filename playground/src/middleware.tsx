import { NextRequest, NextResponse } from 'next/server';

const { NEXT_PUBLIC_AGENT_SERVER_URL, NEXT_PUBLIC_TEN_DEV_SERVER_URL } = process.env;

// Check if environment variables are available
if (!NEXT_PUBLIC_AGENT_SERVER_URL) {
  throw "Environment variables AGENT_SERVER_URL are not available";
}

if (!NEXT_PUBLIC_TEN_DEV_SERVER_URL) {
  throw "Environment variables TEN_DEV_SERVER_URL are not available";
}

const AGENT_SERVER_URL = NEXT_PUBLIC_AGENT_SERVER_URL;
const TEN_DEV_SERVER_URL = NEXT_PUBLIC_TEN_DEV_SERVER_URL;

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const url = req.nextUrl.clone();

  console.log(`The server url is ${AGENT_SERVER_URL}`);

  if (pathname.startsWith(`/api/agents/`)) {
    // Proxy all agents API requests
    url.href = `${AGENT_SERVER_URL}${pathname.replace('/api/agents/', '/')}`;

    try {
      const body = await req.json();
      console.log(`Request to ${pathname} with body ${JSON.stringify(body)}`);
    } catch (e) {
      console.log(`Request to ${pathname} ${e}`);
    }

    return NextResponse.rewrite(url);
  } else if (pathname.startsWith(`/api/vector/`)) {
    // Proxy all vector API requests
    url.href = `${AGENT_SERVER_URL}${pathname.replace('/api/vector/', '/vector/')}`;
    return NextResponse.rewrite(url);
  } else if (pathname.startsWith(`/api/token/`)) {
    // Proxy all token API requests
    url.href = `${AGENT_SERVER_URL}${pathname.replace('/api/token/', '/token/')}`;
    return NextResponse.rewrite(url);
  } else if (pathname.startsWith('/api/dev/')) {
    if (pathname.startsWith('/api/dev/v1/addons/default-properties')) {
      url.href = `${AGENT_SERVER_URL}/dev-tmp/addons/default-properties`;
      console.log(`Rewriting request to ${url.href}`);
      return NextResponse.rewrite(url);
    }

    // Proxy all other dev API requests
    url.href = `${TEN_DEV_SERVER_URL}${pathname.replace('/api/dev/', '/api/designer/')}`;
    return NextResponse.rewrite(url);
  } else {
    // Allow all other requests to proceed as normal
    return NextResponse.next();
  }
}