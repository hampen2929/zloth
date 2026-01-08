import { test as base, Page } from '@playwright/test';

/**
 * Mock API responses for E2E tests
 */
export const mockResponses = {
  models: [] as Array<{
    id: string;
    provider: string;
    model_name: string;
    display_name: string | null;
    created_at: string;
  }>,

  tasks: [] as Array<{
    id: string;
    repo_id: string;
    title: string | null;
    created_at: string;
    updated_at: string;
  }>,

  repos: [
    {
      id: 1,
      name: 'test-repo',
      full_name: 'testuser/test-repo',
      owner: 'testuser',
      default_branch: 'main',
      private: false,
    },
    {
      id: 2,
      name: 'private-repo',
      full_name: 'testuser/private-repo',
      owner: 'testuser',
      default_branch: 'main',
      private: true,
    },
  ],

  preferences: {
    default_repo_owner: null,
    default_repo_name: null,
    default_branch: null,
    default_branch_prefix: null,
    default_pr_creation_mode: 'create',
  },

  branches: [
    { name: 'main', protected: true },
    { name: 'develop', protected: false },
    { name: 'feature/test', protected: false },
  ],
};

/**
 * Setup API mocks for a page
 */
export async function setupApiMocks(page: Page) {
  // Mock /v1/models
  await page.route('**/v1/models', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockResponses.models),
    });
  });

  // Mock /v1/tasks
  await page.route('**/v1/tasks', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockResponses.tasks),
      });
    } else {
      await route.continue();
    }
  });

  // Mock /v1/github/repos
  await page.route('**/v1/github/repos', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockResponses.repos),
    });
  });

  // Mock /v1/preferences
  await page.route('**/v1/preferences', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockResponses.preferences),
    });
  });

  // Mock /v1/github/repos/:owner/:repo/branches
  await page.route('**/v1/github/repos/*/branches', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockResponses.branches),
    });
  });
}

/**
 * Extended test fixture with API mocks
 */
export const test = base.extend<{ mockApi: void }>({
  mockApi: [
    async ({ page }, use) => {
      await setupApiMocks(page);
      await use();
    },
    { auto: true },
  ],
});

export { expect } from '@playwright/test';
