/**
 * OAuth 2.1 Implementation for Google Gmail API
 *
 * Implements OAuth 2.1 with PKCE (Proof Key for Code Exchange) for enhanced security.
 * Handles authorization flow, token exchange, and token refresh.
 */

// Gmail API scopes
export const GMAIL_SCOPES = [
	'https://www.googleapis.com/auth/gmail.readonly',
	'https://www.googleapis.com/auth/gmail.modify',
	'https://www.googleapis.com/auth/gmail.labels',
	'https://www.googleapis.com/auth/userinfo.email',
	'https://www.googleapis.com/auth/userinfo.profile',
];

export interface OAuthConfig {
	clientId: string;
	clientSecret: string;
	redirectUri: string;
}

export interface OAuthTokens {
	accessToken: string;
	refreshToken?: string;
	expiresAt: number; // Unix timestamp in milliseconds
	scope: string;
	tokenType: string;
}

export interface PKCEChallenge {
	codeVerifier: string;
	codeChallenge: string;
}

export class OAuthManager {
	private config: OAuthConfig;

	constructor(config: OAuthConfig) {
		this.config = config;
	}

	/**
	 * Generate PKCE challenge for OAuth 2.1
	 */
	async generatePKCE(): Promise<PKCEChallenge> {
		// Generate random code verifier (43-128 characters)
		const array = new Uint8Array(32);
		crypto.getRandomValues(array);
		const codeVerifier = this.base64URLEncode(array);

		// Generate code challenge (SHA-256 hash of verifier)
		const encoder = new TextEncoder();
		const data = encoder.encode(codeVerifier);
		const hash = await crypto.subtle.digest('SHA-256', data);
		const codeChallenge = this.base64URLEncode(new Uint8Array(hash));

		return { codeVerifier, codeChallenge };
	}

	/**
	 * Generate OAuth authorization URL
	 */
	getAuthorizationUrl(state: string, codeChallenge: string): string {
		const params = new URLSearchParams({
			client_id: this.config.clientId,
			redirect_uri: this.config.redirectUri,
			response_type: 'code',
			scope: GMAIL_SCOPES.join(' '),
			access_type: 'offline', // Request refresh token
			prompt: 'consent', // Force consent screen to get refresh token
			state: state,
			code_challenge: codeChallenge,
			code_challenge_method: 'S256',
		});

		return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
	}

	/**
	 * Exchange authorization code for tokens
	 */
	async exchangeCodeForTokens(code: string, codeVerifier: string): Promise<OAuthTokens> {
		const params = new URLSearchParams({
			client_id: this.config.clientId,
			client_secret: this.config.clientSecret,
			code: code,
			code_verifier: codeVerifier,
			grant_type: 'authorization_code',
			redirect_uri: this.config.redirectUri,
		});

		const response = await fetch('https://oauth2.googleapis.com/token', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded',
			},
			body: params.toString(),
		});

		if (!response.ok) {
			const error = await response.text();
			throw new Error(`Token exchange failed: ${error}`);
		}

		const data = (await response.json()) as any;

		return {
			accessToken: data.access_token,
			refreshToken: data.refresh_token,
			expiresAt: Date.now() + data.expires_in * 1000,
			scope: data.scope,
			tokenType: data.token_type,
		};
	}

	/**
	 * Refresh access token using refresh token
	 */
	async refreshAccessToken(refreshToken: string): Promise<OAuthTokens> {
		const params = new URLSearchParams({
			client_id: this.config.clientId,
			client_secret: this.config.clientSecret,
			refresh_token: refreshToken,
			grant_type: 'refresh_token',
		});

		const response = await fetch('https://oauth2.googleapis.com/token', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded',
			},
			body: params.toString(),
		});

		if (!response.ok) {
			const error = await response.text();
			throw new Error(`Token refresh failed: ${error}`);
		}

		const data = (await response.json()) as any;

		return {
			accessToken: data.access_token,
			refreshToken: refreshToken, // Preserve existing refresh token
			expiresAt: Date.now() + data.expires_in * 1000,
			scope: data.scope,
			tokenType: data.token_type,
		};
	}

	/**
	 * Revoke access token
	 */
	async revokeToken(token: string): Promise<void> {
		const params = new URLSearchParams({
			token: token,
		});

		const response = await fetch('https://oauth2.googleapis.com/revoke', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded',
			},
			body: params.toString(),
		});

		if (!response.ok) {
			const error = await response.text();
			throw new Error(`Token revocation failed: ${error}`);
		}
	}

	/**
	 * Get user info from Google
	 */
	async getUserInfo(accessToken: string): Promise<any> {
		const response = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
			headers: {
				Authorization: `Bearer ${accessToken}`,
			},
		});

		if (!response.ok) {
			const error = await response.text();
			throw new Error(`Failed to get user info: ${error}`);
		}

		return response.json();
	}

	/**
	 * Generate random state for CSRF protection
	 */
	generateState(): string {
		const array = new Uint8Array(32);
		crypto.getRandomValues(array);
		return this.base64URLEncode(array);
	}

	/**
	 * Base64 URL encoding (without padding)
	 */
	private base64URLEncode(buffer: Uint8Array): string {
		const base64 = btoa(String.fromCharCode(...buffer));
		return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
	}
}

/**
 * Check if tokens are expired or about to expire
 */
export function isTokenExpired(expiresAt: number, bufferSeconds: number = 300): boolean {
	return Date.now() >= expiresAt - bufferSeconds * 1000;
}
