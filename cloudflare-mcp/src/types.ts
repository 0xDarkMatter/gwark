/**
 * Type definitions for Gmail MCP Server
 */

export interface Env {
	GMAIL_SESSIONS: DurableObjectNamespace;
	GMAIL_CACHE: KVNamespace;
	GOOGLE_CLIENT_ID: string;
	GOOGLE_CLIENT_SECRET: string;
	ANTHROPIC_API_KEY?: string;
	ENVIRONMENT: string;
	MCP_VERSION: string;
}

export interface SessionState {
	userId?: string;
	email?: string;
	accessToken?: string;
	refreshToken?: string;
	tokenExpiry?: number;
	lastActivity?: number;
}

export interface OAuthState {
	state: string;
	codeVerifier: string;
	createdAt: number;
}
