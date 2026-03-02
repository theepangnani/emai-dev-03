/**
 * Lightweight i18n module for ClassBridge — English + French (Canadian).
 *
 * Design goals:
 *  - No external library dependency
 *  - Locale persisted in localStorage + synced to user profile
 *  - Simple t() function with optional {{param}} interpolation
 *  - useTranslation() hook for React components
 *  - Custom event "localechange" allows components to re-render
 */

export type Locale = 'en' | 'fr';

const translations: Record<Locale, Record<string, string>> = {
  en: {
    // Navigation
    'nav.dashboard': 'Dashboard',
    'nav.courses': 'Courses',
    'nav.tasks': 'Tasks',
    'nav.messages': 'Messages',
    'nav.studyGuides': 'Study Guides',
    'nav.grades': 'Grades',
    'nav.progress': 'Progress',
    'nav.notes': 'Notes',
    'nav.projects': 'Projects',
    'nav.notifications': 'Notifications',
    'nav.documents': 'Documents',
    'nav.settings': 'Settings',
    'nav.logout': 'Sign Out',
    'nav.apiKeys': 'API Keys',
    'nav.account': 'Account',
    'nav.help': 'Help',
    'nav.faq': 'FAQ',

    // Common actions
    'action.save': 'Save',
    'action.cancel': 'Cancel',
    'action.delete': 'Delete',
    'action.edit': 'Edit',
    'action.create': 'Create',
    'action.upload': 'Upload',
    'action.download': 'Download',
    'action.generate': 'Generate',
    'action.search': 'Search',
    'action.filter': 'Filter',
    'action.copy': 'Copy',
    'action.revoke': 'Revoke',
    'action.done': 'Done',

    // Dashboard
    'dashboard.welcome': 'Welcome back',
    'dashboard.todaysFocus': "Today's Focus",
    'dashboard.upcomingDeadlines': 'Upcoming Deadlines',
    'dashboard.recentActivity': 'Recent Activity',

    // Auth
    'auth.login': 'Sign In',
    'auth.register': 'Create Account',
    'auth.logout': 'Sign Out',
    'auth.email': 'Email address',
    'auth.password': 'Password',
    'auth.forgotPassword': 'Forgot password?',

    // API Keys page
    'apiKeys.title': 'API Keys',
    'apiKeys.subtitle': 'Use API keys to access ClassBridge data from external tools (e.g. Claude Desktop, custom integrations)',
    'apiKeys.createBtn': 'Create New API Key',
    'apiKeys.empty': 'No API keys yet. Create one to connect external tools.',
    'apiKeys.colName': 'Name',
    'apiKeys.colPreview': 'Key Preview',
    'apiKeys.colCreated': 'Created',
    'apiKeys.colLastUsed': 'Last Used',
    'apiKeys.colExpires': 'Expires',
    'apiKeys.colStatus': 'Status',
    'apiKeys.colActions': 'Actions',
    'apiKeys.statusActive': 'Active',
    'apiKeys.statusExpired': 'Expired',
    'apiKeys.statusRevoked': 'Revoked',
    'apiKeys.onetimeWarning': 'This key will not be shown again. Copy it now.',

    // Settings
    'settings.account': 'Account Settings',
    'settings.developer': 'Developer',
    'settings.apiKeysDesc': 'Manage API keys for MCP and external tool access.',

    // Errors
    'error.generic': 'Something went wrong. Please try again.',
    'error.notFound': 'Page not found.',
    'error.unauthorized': 'You are not authorized to view this page.',
  },

  fr: {
    // Navigation
    'nav.dashboard': 'Tableau de bord',
    'nav.courses': 'Cours',
    'nav.tasks': 'Tâches',
    'nav.messages': 'Messages',
    'nav.studyGuides': "Guides d'étude",
    'nav.grades': 'Notes',
    'nav.progress': 'Progrès',
    'nav.notes': 'Notes',
    'nav.projects': 'Projets',
    'nav.notifications': 'Notifications',
    'nav.documents': 'Documents',
    'nav.settings': 'Paramètres',
    'nav.logout': 'Se déconnecter',
    'nav.apiKeys': 'Clés API',
    'nav.account': 'Compte',
    'nav.help': 'Aide',
    'nav.faq': 'FAQ',

    // Common actions
    'action.save': 'Sauvegarder',
    'action.cancel': 'Annuler',
    'action.delete': 'Supprimer',
    'action.edit': 'Modifier',
    'action.create': 'Créer',
    'action.upload': 'Téléverser',
    'action.download': 'Télécharger',
    'action.generate': 'Générer',
    'action.search': 'Rechercher',
    'action.filter': 'Filtrer',
    'action.copy': 'Copier',
    'action.revoke': 'Révoquer',
    'action.done': 'Terminé',

    // Dashboard
    'dashboard.welcome': 'Bon retour',
    'dashboard.todaysFocus': "Priorité d'aujourd'hui",
    'dashboard.upcomingDeadlines': 'Échéances à venir',
    'dashboard.recentActivity': 'Activité récente',

    // Auth
    'auth.login': 'Se connecter',
    'auth.register': 'Créer un compte',
    'auth.logout': 'Se déconnecter',
    'auth.email': 'Adresse courriel',
    'auth.password': 'Mot de passe',
    'auth.forgotPassword': 'Mot de passe oublié?',

    // API Keys page
    'apiKeys.title': 'Clés API',
    'apiKeys.subtitle': 'Utilisez des clés API pour accéder aux données de ClassBridge depuis des outils externes (ex. Claude Desktop, intégrations personnalisées)',
    'apiKeys.createBtn': 'Créer une nouvelle clé API',
    'apiKeys.empty': "Aucune clé API pour l'instant. Créez-en une pour connecter des outils externes.",
    'apiKeys.colName': 'Nom',
    'apiKeys.colPreview': 'Aperçu de la clé',
    'apiKeys.colCreated': 'Créée',
    'apiKeys.colLastUsed': 'Dernière utilisation',
    'apiKeys.colExpires': 'Expire',
    'apiKeys.colStatus': 'Statut',
    'apiKeys.colActions': 'Actions',
    'apiKeys.statusActive': 'Active',
    'apiKeys.statusExpired': 'Expirée',
    'apiKeys.statusRevoked': 'Révoquée',
    'apiKeys.onetimeWarning': 'Cette clé ne sera plus affichée. Copiez-la maintenant.',

    // Settings
    'settings.account': 'Paramètres du compte',
    'settings.developer': 'Développeur',
    'settings.apiKeysDesc': "Gérez les clés API pour l'accès MCP et aux outils externes.",

    // Errors
    'error.generic': 'Quelque chose a mal tourné. Veuillez réessayer.',
    'error.notFound': 'Page introuvable.',
    'error.unauthorized': "Vous n'êtes pas autorisé à voir cette page.",
  },
};

let currentLocale: Locale = (localStorage.getItem('locale') as Locale) || 'en';

// Apply locale to <html lang> attribute on load
if (typeof document !== 'undefined') {
  document.documentElement.lang = currentLocale;
}

export function setLocale(locale: Locale): void {
  currentLocale = locale;
  localStorage.setItem('locale', locale);
  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale;
  }
}

export function getLocale(): Locale {
  return currentLocale;
}

/**
 * Translate a key. Falls back to English, then to the raw key if not found.
 * Supports {{param}} interpolation.
 */
export function t(key: string, params?: Record<string, string>): string {
  let text =
    translations[currentLocale]?.[key] ??
    translations['en']?.[key] ??
    key;

  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v);
    }
  }

  return text;
}

/**
 * Minimal hook-like helper.
 * Note: this does NOT cause React re-renders automatically — use the
 * "localechange" custom event (dispatched by LanguageToggle) to trigger
 * re-renders in components that need them.
 */
export function useTranslation() {
  return { t, locale: currentLocale, setLocale };
}
