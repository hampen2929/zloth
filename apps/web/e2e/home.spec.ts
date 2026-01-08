import { test, expect, mockResponses } from './fixtures';

test.describe('Home Page', () => {
  test('should display the main input area', async ({ page }) => {
    await page.goto('/');

    // Check that the main textarea is visible
    const textarea = page.getByRole('textbox', { name: /task instruction/i });
    await expect(textarea).toBeVisible();

    // Check placeholder text
    await expect(textarea).toHaveAttribute(
      'placeholder',
      'Ask dursor to build, fix bugs, explore...'
    );
  });

  test('should display repository selector', async ({ page }) => {
    await page.goto('/');

    // Check that the repository selector button is visible
    const repoButton = page.getByRole('button', { name: /select repository/i });
    await expect(repoButton).toBeVisible();
  });

  test('should have submit button disabled when form is incomplete', async ({ page }) => {
    await page.goto('/');

    // Submit button should be disabled initially (no instruction, no repo selected)
    const submitButton = page.getByRole('button', { name: /submit task/i });
    await expect(submitButton).toBeDisabled();
  });

  test('should allow typing in the textarea', async ({ page }) => {
    await page.goto('/');

    const textarea = page.getByRole('textbox', { name: /task instruction/i });
    await textarea.fill('Fix the login bug');

    await expect(textarea).toHaveValue('Fix the login bug');
  });

  test('should display keyboard shortcut hint', async ({ page }) => {
    await page.goto('/');

    // Check for keyboard shortcut hint text
    const hint = page.getByText(/to submit/i);
    await expect(hint).toBeVisible();
  });

  test('should open repository dropdown and show mocked repos', async ({ page }) => {
    await page.goto('/');

    // Click on repository selector
    const repoButton = page.getByRole('button', { name: /select repository/i });
    await repoButton.click();

    // Check that the search input appears
    const searchInput = page.getByPlaceholder('Search repositories...');
    await expect(searchInput).toBeVisible();

    // Check that mocked repos are displayed
    await expect(page.getByText(mockResponses.repos[0].full_name)).toBeVisible();
    await expect(page.getByText(mockResponses.repos[1].full_name)).toBeVisible();

    // Check that private badge is shown for private repo
    await expect(page.getByText('Private')).toBeVisible();
  });

  test('should select a repository from dropdown', async ({ page }) => {
    await page.goto('/');

    // Click on repository selector
    const repoButton = page.getByRole('button', { name: /select repository/i });
    await repoButton.click();

    // Click on the first repo
    await page.getByText(mockResponses.repos[0].full_name).click();

    // Verify the repo is selected (button text should change)
    await expect(page.getByRole('button', { name: mockResponses.repos[0].full_name })).toBeVisible();
  });

  test('should filter repositories by search', async ({ page }) => {
    await page.goto('/');

    // Open dropdown
    const repoButton = page.getByRole('button', { name: /select repository/i });
    await repoButton.click();

    // Search for "private"
    const searchInput = page.getByPlaceholder('Search repositories...');
    await searchInput.fill('private');

    // Only the private repo should be visible
    await expect(page.getByText(mockResponses.repos[1].full_name)).toBeVisible();
    await expect(page.getByText(mockResponses.repos[0].full_name)).not.toBeVisible();
  });
});
