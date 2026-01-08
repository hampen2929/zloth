import { test, expect } from '@playwright/test';

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

  test('should open repository dropdown when clicked', async ({ page }) => {
    await page.goto('/');

    // Click on repository selector
    const repoButton = page.getByRole('button', { name: /select repository/i });
    await repoButton.click();

    // Check that the search input appears
    const searchInput = page.getByPlaceholder('Search repositories...');
    await expect(searchInput).toBeVisible();
  });
});
