import { test, expect, mockResponses } from './fixtures';

test.describe('Home Page', () => {
  test('should display the main input area and disabled submit', async ({ page }) => {
    await page.goto('/');

    // Check that the main textarea is visible
    const textarea = page.getByRole('textbox', { name: /task instruction/i });
    await expect(textarea).toBeVisible();

    // Check placeholder text
    await expect(textarea).toHaveAttribute(
      'placeholder',
      'Ask zloth to build, fix bugs, explore...'
    );

    // Check that the repository selector button is visible
    const repoButton = page.getByRole('button', { name: /select repository/i });
    await expect(repoButton).toBeVisible();

    // Submit button should be disabled initially (no instruction, no repo selected)
    const submitButton = page.getByRole('button', { name: /submit task/i });
    await expect(submitButton).toBeDisabled();
  });

  test('should enable submit after selecting repo and instruction', async ({ page }) => {
    await page.goto('/');

    const repoButton = page.getByRole('button', { name: /select repository/i });
    await repoButton.click();

    await page.getByText(mockResponses.repos[0].full_name).click();

    const textarea = page.getByRole('textbox', { name: /task instruction/i });
    await textarea.fill('Fix the login bug');

    const submitButton = page.getByRole('button', { name: /submit task/i });
    await expect(submitButton).toBeEnabled();
  });
});
