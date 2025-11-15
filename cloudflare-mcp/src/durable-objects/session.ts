/**
 * Gmail Session Durable Object
 *
 * Manages per-user session state including:
 * - OAuth tokens (access + refresh)
 * - Email cache
 * - MCP protocol state
 */

import { DurableObject } from 'cloudflare:workers';
import { OAuthManager, isTokenExpired, type OAuthTokens } from '../oauth';
import { type Env, type SessionState, type OAuthState } from '../types';

export class GmailSession extends DurableObject<Env> {
	private state: SessionState = {};
	private oauthManager?: OAuthManager;

	constructor(ctx: DurableObjectState, env: Env) {
		super(ctx, env);

		// Initialize OAuth manager
		this.oauthManager = new OAuthManager({
			clientId: env.GOOGLE_CLIENT_ID,
			clientSecret: env.GOOGLE_CLIENT_SECRET,
			redirectUri: `https://${env.ENVIRONMENT === 'development' ? 'localhost:8787' : 'gmail-mcp.your-account.workers.dev'}/oauth/callback`,
		});

		// Load state from storage on initialization
		this.ctx.blockConcurrencyWhile(async () => {
			await this.loadState();
		});
	}

	async fetch(request: Request): Promise<Response> {
		const url = new URL(request.url);

		// Handle OAuth actions
		if (request.method === 'POST') {
			const body = await request.json() as any;

			if (body.action === 'start_oauth') {
				return this.handleStartOAuth();
			}

			if (body.action === 'complete_oauth') {
				return this.handleCompleteOAuth(body.code, body.state);
			}

			// Handle MCP protocol requests
			return this.handleMCPRequest(body);
		}

		// Session info endpoint (for debugging)
		if (url.pathname === '/session') {
			return Response.json({
				hasAuth: !!this.state.accessToken,
				userId: this.state.userId,
				email: this.state.email,
				lastActivity: this.state.lastActivity,
				tokenExpiry: this.state.tokenExpiry,
			});
		}

		return Response.json({ error: 'Method not allowed' }, { status: 405 });
	}

	/**
	 * Start OAuth flow
	 */
	private async handleStartOAuth(): Promise<Response> {
		if (!this.oauthManager) {
			return Response.json({ error: 'OAuth not configured' }, { status: 500 });
		}

		// Generate PKCE challenge
		const pkce = await this.oauthManager.generatePKCE();
		const state = this.oauthManager.generateState();

		// Store PKCE verifier and state
		const oauthState: OAuthState = {
			state,
			codeVerifier: pkce.codeVerifier,
			createdAt: Date.now(),
		};
		await this.ctx.storage.put('oauth_state', oauthState);

		// Generate authorization URL
		// Include session ID in state parameter
		const sessionId = await this.ctx.storage.get<string>('session_id') || 'default';
		const fullState = `${sessionId}:${state}`;
		const authUrl = this.oauthManager.getAuthorizationUrl(fullState, pkce.codeChallenge);

		return Response.json({ authUrl });
	}

	/**
	 * Complete OAuth flow after callback
	 */
	private async handleCompleteOAuth(code: string, state: string): Promise<Response> {
		if (!this.oauthManager) {
			return Response.json({ error: 'OAuth not configured' }, { status: 500 });
		}

		// Retrieve stored OAuth state
		const oauthState = await this.ctx.storage.get<OAuthState>('oauth_state');
		if (!oauthState) {
			return Response.json({ error: 'OAuth state not found' }, { status: 400 });
		}

		// Verify state matches
		if (oauthState.state !== state) {
			return Response.json({ error: 'State mismatch - possible CSRF attack' }, { status: 400 });
		}

		// Check state is not too old (10 minutes)
		if (Date.now() - oauthState.createdAt > 10 * 60 * 1000) {
			return Response.json({ error: 'OAuth state expired' }, { status: 400 });
		}

		try {
			// Exchange code for tokens
			const tokens = await this.oauthManager.exchangeCodeForTokens(code, oauthState.codeVerifier);

			// Get user info
			const userInfo = await this.oauthManager.getUserInfo(tokens.accessToken);

			// Store tokens
			this.state.accessToken = tokens.accessToken;
			this.state.refreshToken = tokens.refreshToken;
			this.state.tokenExpiry = tokens.expiresAt;
			this.state.userId = userInfo.id;
			this.state.email = userInfo.email;
			this.state.lastActivity = Date.now();

			await this.saveState();

			// Clean up OAuth state
			await this.ctx.storage.delete('oauth_state');

			return Response.json({
				success: true,
				email: userInfo.email,
				userId: userInfo.id,
			});
		} catch (error) {
			return Response.json({
				error: error instanceof Error ? error.message : 'OAuth failed',
			}, { status: 500 });
		}
	}

	/**
	 * Ensure valid access token (refresh if needed)
	 */
	private async ensureValidToken(): Promise<string | null> {
		if (!this.oauthManager) {
			return null;
		}

		// No token at all
		if (!this.state.accessToken) {
			return null;
		}

		// Token still valid
		if (this.state.tokenExpiry && !isTokenExpired(this.state.tokenExpiry)) {
			return this.state.accessToken;
		}

		// Need to refresh
		if (!this.state.refreshToken) {
			// No refresh token, need to re-authenticate
			return null;
		}

		try {
			const tokens = await this.oauthManager.refreshAccessToken(this.state.refreshToken);

			this.state.accessToken = tokens.accessToken;
			this.state.tokenExpiry = tokens.expiresAt;
			this.state.lastActivity = Date.now();

			await this.saveState();

			return tokens.accessToken;
		} catch (error) {
			console.error('Token refresh failed:', error);
			return null;
		}
	}

	/**
	 * Handle MCP protocol requests
	 */
	private async handleMCPRequest(body: any): Promise<Response> {
		try {
			// MCP protocol: https://spec.modelcontextprotocol.io/
			const { method, params } = body;

			switch (method) {
				case 'initialize':
					return this.handleInitialize(params);

				case 'tools/list':
					return this.handleToolsList();

				case 'tools/call':
					return this.handleToolCall(params);

				default:
					return Response.json({
						error: { code: -32601, message: `Method not found: ${method}` },
					});
			}
		} catch (error) {
			return Response.json({
				error: {
					code: -32700,
					message: 'Parse error',
					data: error instanceof Error ? error.message : 'Unknown error',
				},
			});
		}
	}

	/**
	 * Handle MCP initialize request
	 */
	private async handleInitialize(params: any): Promise<Response> {
		return Response.json({
			protocolVersion: '2024-11-05',
			capabilities: {
				tools: {},
			},
			serverInfo: {
				name: 'gmail-mcp',
				version: '0.2.0',
			},
		});
	}

	/**
	 * List available MCP tools
	 */
	private async handleToolsList(): Promise<Response> {
		return Response.json({
			tools: [
				{
					name: 'search_emails',
					description: 'Search Gmail emails with filters and pagination',
					inputSchema: {
						type: 'object',
						properties: {
							query: {
								type: 'string',
								description: 'Gmail search query (e.g., "from:user@example.com")',
							},
							maxResults: {
								type: 'number',
								description: 'Maximum number of results to return',
								default: 10,
							},
						},
						required: ['query'],
					},
				},
				{
					name: 'read_email',
					description: 'Read a specific email by ID',
					inputSchema: {
						type: 'object',
						properties: {
							emailId: {
								type: 'string',
								description: 'Gmail message ID',
							},
						},
						required: ['emailId'],
					},
				},
				{
					name: 'get_profile',
					description: 'Get Gmail user profile information',
					inputSchema: {
						type: 'object',
						properties: {},
					},
				},
			],
		});
	}

	/**
	 * Execute an MCP tool call
	 */
	private async handleToolCall(params: any): Promise<Response> {
		const { name, arguments: args } = params;

		// Ensure valid access token
		const accessToken = await this.ensureValidToken();
		if (!accessToken) {
			return Response.json({
				error: {
					code: -32000,
					message: 'Not authenticated. Please authenticate with Gmail first.',
					data: {
						authRequired: true,
						authUrl: '/oauth/authorize',
					},
				},
			});
		}

		// Route to appropriate tool handler
		switch (name) {
			case 'search_emails':
				return this.toolSearchEmails(args);

			case 'read_email':
				return this.toolReadEmail(args);

			case 'get_profile':
				return this.toolGetProfile(args);

			default:
				return Response.json({
					error: {
						code: -32601,
						message: `Tool not found: ${name}`,
					},
				});
		}
	}

	/**
	 * Tool: Search emails
	 */
	private async toolSearchEmails(args: any): Promise<Response> {
		// TODO: Implement Gmail API search
		return Response.json({
			content: [
				{
					type: 'text',
					text: 'Email search not yet implemented. Coming soon!',
				},
			],
		});
	}

	/**
	 * Tool: Read email
	 */
	private async toolReadEmail(args: any): Promise<Response> {
		// TODO: Implement Gmail API read
		return Response.json({
			content: [
				{
					type: 'text',
					text: 'Email reading not yet implemented. Coming soon!',
				},
			],
		});
	}

	/**
	 * Tool: Get profile
	 */
	private async toolGetProfile(args: any): Promise<Response> {
		// TODO: Implement Gmail API profile
		return Response.json({
			content: [
				{
					type: 'text',
					text: 'Profile retrieval not yet implemented. Coming soon!',
				},
			],
		});
	}

	/**
	 * Save session state to storage
	 */
	private async saveState(): Promise<void> {
		await this.ctx.storage.put('session_state', this.state);
	}

	/**
	 * Load session state from storage
	 */
	private async loadState(): Promise<void> {
		const stored = await this.ctx.storage.get<SessionState>('session_state');
		if (stored) {
			this.state = stored;
		}
	}
}
