/**
 * Gmail MCP Server for Cloudflare Workers
 *
 * This server provides Model Context Protocol (MCP) tools for Gmail integration.
 * It uses Cloudflare Durable Objects for session management and OAuth token storage.
 */

import { GmailSession } from './durable-objects/session';
import { Env } from './types';

export { GmailSession };

export default {
	async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
		const url = new URL(request.url);

		// CORS headers for MCP clients
		const corsHeaders = {
			'Access-Control-Allow-Origin': '*',
			'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
			'Access-Control-Allow-Headers': 'Content-Type, Authorization',
		};

		// Handle CORS preflight
		if (request.method === 'OPTIONS') {
			return new Response(null, { headers: corsHeaders });
		}

		// Health check endpoint
		if (url.pathname === '/health') {
			return Response.json(
				{
					status: 'ok',
					version: env.MCP_VERSION,
					environment: env.ENVIRONMENT,
				},
				{ headers: corsHeaders }
			);
		}

		// OAuth endpoints
		if (url.pathname === '/oauth/authorize') {
			return this.handleOAuthAuthorize(request, env);
		}

		if (url.pathname === '/oauth/callback') {
			return this.handleOAuthCallback(request, env);
		}

		// MCP endpoint
		if (url.pathname === '/mcp' || url.pathname === '/') {
			// Get or create session for this client
			const sessionId = this.getSessionId(request);
			const durableObjectId = env.GMAIL_SESSIONS.idFromName(sessionId);
			const durableObject = env.GMAIL_SESSIONS.get(durableObjectId);

			// Forward request to Durable Object
			return durableObject.fetch(request);
		}

		// 404 for unknown routes
		return Response.json(
			{ error: 'Not found' },
			{ status: 404, headers: corsHeaders }
		);
	},

	/**
	 * Handle OAuth authorization redirect
	 */
	async handleOAuthAuthorize(request: Request, env: Env): Promise<Response> {
		// Get or create session
		const sessionId = this.getSessionId(request);
		const durableObjectId = env.GMAIL_SESSIONS.idFromName(sessionId);
		const durableObject = env.GMAIL_SESSIONS.get(durableObjectId);

		// Forward to Durable Object to generate OAuth URL
		const authRequest = new Request(request.url, {
			method: 'POST',
			body: JSON.stringify({ action: 'start_oauth' }),
		});

		return durableObject.fetch(authRequest);
	},

	/**
	 * Handle OAuth callback from Google
	 */
	async handleOAuthCallback(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);
		const code = url.searchParams.get('code');
		const state = url.searchParams.get('state');
		const error = url.searchParams.get('error');

		// Check for OAuth errors
		if (error) {
			return new Response(
				`
<!DOCTYPE html>
<html>
<head><title>OAuth Error</title></head>
<body>
	<h1>Authentication Failed</h1>
	<p>Error: ${error}</p>
	<p>${url.searchParams.get('error_description') || ''}</p>
	<a href="/">Try Again</a>
</body>
</html>`,
				{
					headers: { 'Content-Type': 'text/html' },
					status: 400,
				}
			);
		}

		if (!code || !state) {
			return new Response('Missing code or state parameter', { status: 400 });
		}

		// Extract session ID from state
		// State format: "sessionId:randomState"
		const [sessionId, randomState] = state.split(':');
		if (!sessionId || !randomState) {
			return new Response('Invalid state parameter', { status: 400 });
		}

		// Get Durable Object for this session
		const durableObjectId = env.GMAIL_SESSIONS.idFromName(sessionId);
		const durableObject = env.GMAIL_SESSIONS.get(durableObjectId);

		// Forward callback to Durable Object
		const callbackRequest = new Request(request.url, {
			method: 'POST',
			body: JSON.stringify({
				action: 'complete_oauth',
				code,
				state: randomState,
			}),
		});

		const response = await durableObject.fetch(callbackRequest);
		const result = await response.json() as any;

		if (result.error) {
			return new Response(
				`
<!DOCTYPE html>
<html>
<head><title>OAuth Error</title></head>
<body>
	<h1>Authentication Failed</h1>
	<p>${result.error}</p>
	<a href="/oauth/authorize">Try Again</a>
</body>
</html>`,
				{
					headers: { 'Content-Type': 'text/html' },
					status: 400,
				}
			);
		}

		// Success! Show success page
		return new Response(
			`
<!DOCTYPE html>
<html>
<head><title>OAuth Success</title></head>
<body>
	<h1>Authentication Successful!</h1>
	<p>You have successfully authenticated with Gmail.</p>
	<p>Email: ${result.email}</p>
	<p>You can now close this window and return to Claude Desktop.</p>
	<script>
		// Auto-close window after 3 seconds
		setTimeout(() => window.close(), 3000);
	</script>
</body>
</html>`,
			{
				headers: { 'Content-Type': 'text/html' },
			}
		);
	},

	/**
	 * Extract or generate session ID from request
	 */
	getSessionId(request: Request): string {
		// Try to get session from Authorization header
		const authHeader = request.headers.get('Authorization');
		if (authHeader?.startsWith('Bearer ')) {
			const token = authHeader.substring(7);
			// For now, use token as session ID
			// In production, validate and decode the token
			return token;
		}

		// Try to get from cookie
		const cookies = request.headers.get('Cookie');
		if (cookies) {
			const sessionMatch = cookies.match(/session=([^;]+)/);
			if (sessionMatch) {
				return sessionMatch[1];
			}
		}

		// Generate new session ID
		const array = new Uint8Array(16);
		crypto.getRandomValues(array);
		return Array.from(array, (byte) => byte.toString(16).padStart(2, '0')).join('');
	},
} satisfies ExportedHandler<Env>;
