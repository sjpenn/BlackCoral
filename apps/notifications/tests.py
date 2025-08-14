"""
BLACK CORAL Notification System Tests
Test notification creation, delivery, and management
"""

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock

from apps.notifications.models import (
    Notification, NotificationPreference, NotificationTemplate,
    NotificationDigest, AlertRule, WebhookEndpoint
)
from apps.notifications.services import notification_service

User = get_user_model()


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@blackcoral.ai',
            first_name='Test',
            last_name='User',
            password='testpass123'
        )

    def test_create_basic_notification(self):
        """Test creating a basic notification"""
        notification = notification_service.create_notification(
            user=self.user,
            notification_type='system_update',
            title='Test Notification',
            message='This is a test notification',
            priority='medium'
        )
        
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.title, 'Test Notification')
        self.assertEqual(notification.message, 'This is a test notification')
        self.assertEqual(notification.priority, 'medium')
        self.assertEqual(notification.status, 'pending')

    def test_notification_with_template(self):
        """Test creating notification using template"""
        # Create a template
        template = NotificationTemplate.objects.create(
            notification_type='task_assigned',
            title_template='Task: {task_title}',
            message_template='You have been assigned task: {task_title}',
            default_priority='high'
        )
        
        notification = notification_service.create_notification(
            user=self.user,
            notification_type='task_assigned',
            metadata={'task_title': 'Write proposal section'}
        )
        
        self.assertEqual(notification.title, 'Task: Write proposal section')
        self.assertEqual(notification.message, 'You have been assigned task: Write proposal section')

    def test_mark_notification_read(self):
        """Test marking notification as read"""
        notification = notification_service.create_notification(
            user=self.user,
            notification_type='system_update',
            title='Test Notification',
            message='Test message'
        )
        
        self.assertFalse(notification.is_read)
        
        success = notification_service.mark_notification_read(notification.id, self.user)
        
        self.assertTrue(success)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_get_unread_count(self):
        """Test getting unread notification count"""
        # Create some notifications
        notification1 = notification_service.create_notification(
            user=self.user,
            notification_type='system_update',
            title='Unread 1',
            message='Message 1'
        )
        # Mark as sent to be counted as unread
        notification1.status = 'sent'
        notification1.save()
        
        notification2 = notification_service.create_notification(
            user=self.user,
            notification_type='system_update',
            title='Unread 2',
            message='Message 2'
        )
        # Mark as sent then read
        notification2.status = 'sent'
        notification2.save()
        notification2.mark_as_read()
        
        unread_count = notification_service.get_unread_count(self.user)
        self.assertEqual(unread_count, 1)

    def test_notify_multiple_users(self):
        """Test notifying multiple users"""
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@blackcoral.ai',
            first_name='Test2',
            last_name='User2',
            password='testpass123'
        )
        
        notifications = notification_service.notify_multiple_users(
            users=[self.user, user2],
            notification_type='system_update',
            title='Broadcast Message',
            message='Message for all users'
        )
        
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].user, self.user)
        self.assertEqual(notifications[1].user, user2)

    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    })
    @patch('apps.notifications.services.send_mail')
    def test_email_notification_delivery(self, mock_send_mail):
        """Test email notification delivery"""
        # Create preference for email notifications
        NotificationPreference.objects.create(
            user=self.user,
            notification_type='system_update',
            delivery_method='email',
            is_enabled=True,
            immediate=True
        )
        
        # Mock successful email sending
        mock_send_mail.return_value = True
        
        notification = notification_service.create_notification(
            user=self.user,
            notification_type='system_update',
            title='Email Test',
            message='This should be sent via email'
        )
        
        # Check that email was sent (should be called during creation due to immediate preference)
        self.assertTrue(mock_send_mail.called)
        
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'sent')


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@blackcoral.ai',
            first_name='Test',
            last_name='User',
            password='testpass123'
        )

    def test_notification_expiration(self):
        """Test notification expiration functionality"""
        # Create expired notification
        expired_notification = Notification.objects.create(
            user=self.user,
            notification_type='system_update',
            title='Expired Notification',
            message='This notification has expired',
            expires_at=timezone.now() - timezone.timedelta(hours=1)
        )
        
        # Create active notification
        active_notification = Notification.objects.create(
            user=self.user,
            notification_type='system_update',
            title='Active Notification',
            message='This notification is still active',
            expires_at=timezone.now() + timezone.timedelta(hours=1)
        )
        
        self.assertTrue(expired_notification.is_expired)
        self.assertFalse(active_notification.is_expired)

    def test_notification_preferences(self):
        """Test notification preference model"""
        preference = NotificationPreference.objects.create(
            user=self.user,
            notification_type='task_assigned',
            delivery_method='email',
            is_enabled=True,
            immediate=True,
            daily_digest=False
        )
        
        self.assertEqual(preference.user, self.user)
        self.assertEqual(preference.notification_type, 'task_assigned')
        self.assertEqual(preference.delivery_method, 'email')
        self.assertTrue(preference.is_enabled)

    def test_notification_template_rendering(self):
        """Test notification template rendering"""
        template = NotificationTemplate.objects.create(
            notification_type='task_assigned',
            title_template='Task: {task_title}',
            message_template='Hello {user_name}, you have been assigned: {task_title}',
            email_subject_template='New Task: {task_title}',
            email_body_template='Hi {user_first_name},\n\nTask: {task_title}\n\nBest regards,\nTeam'
        )
        
        context = {
            'user_name': 'John Doe',
            'user_first_name': 'John',
            'task_title': 'Write proposal'
        }
        
        title = template.render_title(context)
        message = template.render_message(context)
        email_subject = template.render_email_subject(context)
        email_body = template.render_email_body(context)
        
        self.assertEqual(title, 'Task: Write proposal')
        self.assertEqual(message, 'Hello John Doe, you have been assigned: Write proposal')
        self.assertEqual(email_subject, 'New Task: Write proposal')
        self.assertIn('Hi John', email_body)
        self.assertIn('Write proposal', email_body)

    def test_alert_rule_can_trigger(self):
        """Test alert rule triggering logic"""
        rule = AlertRule.objects.create(
            name='Test Alert Rule',
            trigger_type='task_overdue',
            notification_type='task_overdue',
            priority='high',
            message_template='Alert: {message}',
            max_frequency_hours=24,
            is_active=True
        )
        
        # Should be able to trigger initially
        self.assertTrue(rule.can_trigger())
        
        # Mark as triggered
        rule.trigger()
        
        # Should not be able to trigger again immediately
        self.assertFalse(rule.can_trigger())
        
        # Should be able to trigger after frequency period
        rule.last_triggered = timezone.now() - timezone.timedelta(hours=25)
        rule.save()
        self.assertTrue(rule.can_trigger())

    def test_webhook_endpoint_success_rate(self):
        """Test webhook endpoint success rate calculation"""
        endpoint = WebhookEndpoint.objects.create(
            name='Test Webhook',
            service_type='slack',
            webhook_url='https://hooks.slack.com/test',
            success_count=80,
            failure_count=20
        )
        
        self.assertEqual(endpoint.success_rate, 80.0)
        
        # Test with no attempts
        endpoint.success_count = 0
        endpoint.failure_count = 0
        self.assertEqual(endpoint.success_rate, 0)


class NotificationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@blackcoral.ai',
            first_name='Test',
            last_name='User',
            password='testpass123'
        )
        self.client.force_login(self.user)

    def test_notification_center_view(self):
        """Test notification center view"""
        # Create some notifications
        notification_service.create_notification(
            user=self.user,
            notification_type='system_update',
            title='Test Notification 1',
            message='Message 1'
        )
        
        notification_service.create_notification(
            user=self.user,
            notification_type='task_assigned',
            title='Test Notification 2',
            message='Message 2'
        )
        
        response = self.client.get('/notifications/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Notification 1')
        self.assertContains(response, 'Test Notification 2')

    def test_mark_notification_read_view(self):
        """Test marking notification as read via view"""
        notification = notification_service.create_notification(
            user=self.user,
            notification_type='system_update',
            title='Test Notification',
            message='Test message'
        )
        
        response = self.client.post(f'/notifications/mark-read/{notification.id}/')
        
        self.assertEqual(response.status_code, 200)
        
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_notification_stats_api(self):
        """Test notification statistics API"""
        # Create some notifications
        for i in range(5):
            notification_service.create_notification(
                user=self.user,
                notification_type='system_update',
                title=f'Notification {i}',
                message=f'Message {i}'
            )
        
        response = self.client.get('/notifications/api/stats/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('total_unread', data)
        self.assertIn('today', data)
        self.assertIn('by_type', data)


class NotificationSignalTests(TestCase):
    """Test notification signals and automatic triggers"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@blackcoral.ai',
            first_name='Test',
            last_name='User',
            password='testpass123'
        )

    @patch('apps.notifications.signals.notification_service.create_notification')
    def test_team_creation_signal(self, mock_create_notification):
        """Test that team creation triggers notification"""
        from apps.collaboration.models import ProposalTeam
        from apps.opportunities.models import Opportunity
        
        # Create an opportunity
        opportunity = Opportunity.objects.create(
            solicitation_number='TEST-001',
            title='Test Opportunity',
            description='Test description',
            estimated_value=100000
        )
        
        # Create a team
        team = ProposalTeam.objects.create(
            opportunity=opportunity,
            name='Test Team',
            lead=self.user
        )
        
        # Check that notification was triggered
        mock_create_notification.assert_called()
        call_args = mock_create_notification.call_args
        
        self.assertEqual(call_args[1]['user'], self.user)
        self.assertEqual(call_args[1]['notification_type'], 'team_assignment')
        self.assertIn('lead', call_args[1]['title'])


# Integration test with real database
class NotificationIntegrationTests(TestCase):
    """Integration tests for the complete notification system"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@blackcoral.ai',
            first_name='Test',
            last_name='User',
            password='testpass123'
        )

    def test_full_notification_workflow(self):
        """Test complete notification workflow from creation to delivery"""
        # Create preference
        NotificationPreference.objects.create(
            user=self.user,
            notification_type='system_update',
            delivery_method='in_app',
            is_enabled=True,
            immediate=True
        )
        
        # Create template
        NotificationTemplate.objects.create(
            notification_type='system_update',
            title_template='System Alert: {alert_type}',
            message_template='Alert: {message}',
            default_priority='medium'
        )
        
        # Create notification
        notification = notification_service.create_notification(
            user=self.user,
            notification_type='system_update',
            metadata={
                'alert_type': 'Maintenance',
                'message': 'System maintenance scheduled'
            }
        )
        
        # Verify notification was created with template
        self.assertEqual(notification.title, 'System Alert: Maintenance')
        self.assertEqual(notification.message, 'Alert: System maintenance scheduled')
        
        # Mark as read
        success = notification_service.mark_notification_read(notification.id, self.user)
        self.assertTrue(success)
        
        # Verify status
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertEqual(notification.status, 'read')


if __name__ == '__main__':
    import django
    django.setup()
    
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["apps.notifications"])
    
    if failures:
        exit(1)