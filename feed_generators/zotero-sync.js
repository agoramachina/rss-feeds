/**
 * Zotero Actions and Tags Script
 * Triggers GitHub Action to regenerate RSS feeds
 *
 * Setup:
 * 1. Create a GitHub Personal Access Token with 'repo' scope
 * 2. Set the token below or use environment variable
 * 3. Add this script to Zotero Actions and Tags plugin
 * 4. Configure to run on Zotero startup or manually
 */

const GITHUB_TOKEN = "YOUR_GITHUB_TOKEN_HERE"; // or use Zotero.Prefs.get('extensions.zotero-actions-tags.githubToken')
const REPO_OWNER = "agoramachina";
const REPO_NAME = "rss-feeds";
const WORKFLOW_FILE = "run_feeds.yml";
const BRANCH = "main";

async function triggerFeedSync() {
    const url = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": `Bearer ${GITHUB_TOKEN}`,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                ref: BRANCH
            })
        });

        if (response.status === 204) {
            // Success - GitHub returns 204 No Content on successful dispatch
            Zotero.debug("[RSS Feeds] Successfully triggered feed regeneration");
            return { success: true, message: "Feed sync triggered successfully" };
        } else {
            const error = await response.text();
            Zotero.debug(`[RSS Feeds] Failed to trigger: ${response.status} - ${error}`);
            return { success: false, message: `Failed: ${response.status}` };
        }
    } catch (err) {
        Zotero.debug(`[RSS Feeds] Error triggering sync: ${err.message}`);
        return { success: false, message: err.message };
    }
}

// Execute
return triggerFeedSync();
