"""Notification service for agentic execution events."""

import logging
from abc import ABC, abstractmethod

import httpx

from dursor_api.config import settings
from dursor_api.domain.enums import NotificationType
from dursor_api.domain.models import NotificationEvent

logger = logging.getLogger(__name__)


class NotificationChannel(ABC):
    """Abstract base for notification channels."""

    @abstractmethod
    async def send(self, event: NotificationEvent) -> bool:
        """Send notification via this channel.

        Args:
            event: The notification event to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        pass


class SlackNotifier(NotificationChannel):
    """Slack Webhook notification channel."""

    def __init__(self, webhook_url: str):
        """Initialize Slack notifier.

        Args:
            webhook_url: Slack incoming webhook URL.
        """
        self.webhook_url = webhook_url

    async def send(self, event: NotificationEvent) -> bool:
        """Send notification to Slack.

        Args:
            event: The notification event to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.webhook_url:
            logger.debug("Slack webhook URL not configured, skipping notification")
            return False

        color = {
            NotificationType.READY_FOR_MERGE: "#36a64f",  # Green
            NotificationType.COMPLETED: "#2eb886",  # Teal
            NotificationType.FAILED: "#dc3545",  # Red
            NotificationType.WARNING: "#ffc107",  # Yellow
        }.get(event.type, "#6c757d")

        mode_display = event.mode.value if event.mode else "Unknown"
        type_display = event.type.value.replace("_", " ").title()

        fields = [
            {"title": "Task", "value": event.task_title or event.task_id, "short": True},
            {"title": "Iterations", "value": str(event.iterations), "short": True},
        ]

        if event.review_score is not None:
            fields.append(
                {
                    "title": "Review Score",
                    "value": f"{event.review_score:.2f}",
                    "short": True,
                }
            )

        if event.error:
            fields.append(
                {
                    "title": "Error",
                    "value": event.error[:200],  # Truncate long errors
                    "short": False,
                }
            )

        payload: dict[str, list[dict[str, object]]] = {
            "attachments": [
                {
                    "color": color,
                    "title": f"[{mode_display}] {type_display}",
                    "text": event.message,
                    "fields": fields,
                }
            ]
        }

        # Add action button if PR URL is available
        if event.pr_url and event.pr_number:
            payload["attachments"][0]["actions"] = [
                {
                    "type": "button",
                    "text": f"View PR #{event.pr_number}",
                    "url": event.pr_url,
                }
            ]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=10.0)
                success = response.status_code == 200
                if not success:
                    logger.warning(f"Slack notification failed: {response.status_code}")
                return success
        except Exception as e:
            logger.error(f"Slack notification error: {e}")
            return False


class LogNotifier(NotificationChannel):
    """Log-based notification channel for development/testing."""

    async def send(self, event: NotificationEvent) -> bool:
        """Log the notification event.

        Args:
            event: The notification event to log.

        Returns:
            Always returns True.
        """
        log_level = {
            NotificationType.READY_FOR_MERGE: logging.INFO,
            NotificationType.COMPLETED: logging.INFO,
            NotificationType.FAILED: logging.ERROR,
            NotificationType.WARNING: logging.WARNING,
        }.get(event.type, logging.INFO)

        logger.log(
            log_level,
            f"[Notification] {event.type.value}: {event.message} "
            f"(task={event.task_id}, iterations={event.iterations})",
        )
        return True


class NotificationService:
    """Manages multiple notification channels for agentic events."""

    def __init__(self, channels: list[NotificationChannel] | None = None):
        """Initialize notification service.

        Args:
            channels: List of notification channels. If None, creates default channels.
        """
        if channels is not None:
            self.channels = channels
        else:
            self.channels = self._create_default_channels()

    def _create_default_channels(self) -> list[NotificationChannel]:
        """Create default notification channels based on settings.

        Returns:
            List of configured notification channels.
        """
        channels: list[NotificationChannel] = []

        # Always add log notifier
        channels.append(LogNotifier())

        # Add Slack if configured
        if settings.slack_webhook_url:
            channels.append(SlackNotifier(settings.slack_webhook_url))

        return channels

    async def send(self, event: NotificationEvent) -> dict[str, bool]:
        """Send notification to all configured channels.

        Args:
            event: The notification event to send.

        Returns:
            Dictionary mapping channel names to success status.
        """
        # Check if notification should be sent based on settings
        if not self._should_notify(event.type):
            logger.debug(f"Notification type {event.type} disabled in settings")
            return {}

        results: dict[str, bool] = {}
        for channel in self.channels:
            channel_name = channel.__class__.__name__
            try:
                results[channel_name] = await channel.send(event)
            except Exception as e:
                logger.error(f"Notification failed for {channel_name}: {e}")
                results[channel_name] = False

        return results

    def _should_notify(self, notification_type: NotificationType) -> bool:
        """Check if notification should be sent based on settings.

        Args:
            notification_type: The type of notification.

        Returns:
            True if notification should be sent.
        """
        type_to_setting = {
            NotificationType.READY_FOR_MERGE: settings.notify_on_ready,
            NotificationType.COMPLETED: settings.notify_on_complete,
            NotificationType.FAILED: settings.notify_on_failure,
            NotificationType.WARNING: settings.notify_on_warning,
        }
        return type_to_setting.get(notification_type, True)

    async def notify_ready_for_merge(
        self,
        task_id: str,
        task_title: str | None,
        pr_number: int,
        pr_url: str,
        mode: str,
        iterations: int,
        review_score: float | None,
    ) -> dict[str, bool]:
        """Send ready-for-merge notification.

        Args:
            task_id: Task ID.
            task_title: Task title.
            pr_number: PR number.
            pr_url: PR URL.
            mode: Coding mode.
            iterations: Number of iterations.
            review_score: Review score.

        Returns:
            Dictionary mapping channel names to success status.
        """
        from dursor_api.domain.enums import CodingMode

        event = NotificationEvent(
            type=NotificationType.READY_FOR_MERGE,
            task_id=task_id,
            task_title=task_title,
            pr_number=pr_number,
            pr_url=pr_url,
            message=f"PR #{pr_number} is ready for your review and merge.",
            mode=CodingMode(mode) if mode else None,
            iterations=iterations,
            review_score=review_score,
        )
        return await self.send(event)

    async def notify_completed(
        self,
        task_id: str,
        task_title: str | None,
        pr_number: int,
        pr_url: str,
        mode: str,
        iterations: int,
    ) -> dict[str, bool]:
        """Send completion notification.

        Args:
            task_id: Task ID.
            task_title: Task title.
            pr_number: PR number.
            pr_url: PR URL.
            mode: Coding mode.
            iterations: Number of iterations.

        Returns:
            Dictionary mapping channel names to success status.
        """
        from dursor_api.domain.enums import CodingMode

        event = NotificationEvent(
            type=NotificationType.COMPLETED,
            task_id=task_id,
            task_title=task_title,
            pr_number=pr_number,
            pr_url=pr_url,
            message=f"PR #{pr_number} has been merged successfully.",
            mode=CodingMode(mode) if mode else None,
            iterations=iterations,
        )
        return await self.send(event)

    async def notify_failed(
        self,
        task_id: str,
        task_title: str | None,
        error: str,
        mode: str | None,
        iterations: int,
        pr_number: int | None = None,
    ) -> dict[str, bool]:
        """Send failure notification.

        Args:
            task_id: Task ID.
            task_title: Task title.
            error: Error message.
            mode: Coding mode.
            iterations: Number of iterations.
            pr_number: PR number if available.

        Returns:
            Dictionary mapping channel names to success status.
        """
        from dursor_api.domain.enums import CodingMode

        event = NotificationEvent(
            type=NotificationType.FAILED,
            task_id=task_id,
            task_title=task_title,
            pr_number=pr_number,
            message=f"Task failed: {error}",
            mode=CodingMode(mode) if mode else None,
            iterations=iterations,
            error=error,
        )
        return await self.send(event)

    async def notify_warning(
        self,
        task_id: str,
        task_title: str | None,
        message: str,
        mode: str,
        iterations: int,
        pr_number: int | None = None,
    ) -> dict[str, bool]:
        """Send warning notification.

        Args:
            task_id: Task ID.
            task_title: Task title.
            message: Warning message.
            mode: Coding mode.
            iterations: Number of iterations.
            pr_number: PR number if available.

        Returns:
            Dictionary mapping channel names to success status.
        """
        from dursor_api.domain.enums import CodingMode

        event = NotificationEvent(
            type=NotificationType.WARNING,
            task_id=task_id,
            task_title=task_title,
            pr_number=pr_number,
            message=message,
            mode=CodingMode(mode) if mode else None,
            iterations=iterations,
        )
        return await self.send(event)
