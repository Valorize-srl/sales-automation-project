import { NextRequest, NextResponse } from "next/server";
import { createToken, getAuthCookieConfig } from "@/lib/auth";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { password } = body;

    if (!password) {
      return NextResponse.json(
        { error: "Password is required" },
        { status: 400 }
      );
    }

    const authPassword = process.env.AUTH_PASSWORD;
    if (!authPassword) {
      console.error("AUTH_PASSWORD environment variable is not set");
      return NextResponse.json(
        { error: "Server configuration error" },
        { status: 500 }
      );
    }

    if (password !== authPassword) {
      return NextResponse.json(
        { error: "Invalid password" },
        { status: 401 }
      );
    }

    const token = await createToken();
    const cookieConfig = getAuthCookieConfig(token);

    const response = NextResponse.json({ success: true });
    response.cookies.set(cookieConfig);

    return response;
  } catch {
    return NextResponse.json(
      { error: "Invalid request" },
      { status: 400 }
    );
  }
}
