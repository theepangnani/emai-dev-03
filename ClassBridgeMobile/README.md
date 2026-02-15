# ClassBridge Mobile App

React Native mobile application for the ClassBridge education platform (iOS & Android).

## 📱 Tech Stack

- **Framework:** React Native (via Expo SDK 54)
- **Language:** TypeScript 5.9
- **Navigation:** React Navigation 7
- **State Management:** TanStack React Query 5
- **API Client:** Axios
- **UI:** React Native Components + @expo/vector-icons
- **Push Notifications:** Firebase Cloud Messaging
- **Storage:** AsyncStorage

## 🚀 Quick Start

### Prerequisites

```bash
# Required
Node.js >= 18
npm >= 9

# Optional (for native builds)
Xcode (macOS only) - for iOS development
Android Studio - for Android development
```

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm start
```

### Running the App

**Option 1: Expo Go (Recommended for development)**
1. Install Expo Go app on your phone ([iOS](https://apps.apple.com/app/expo-go/id982107779) | [Android](https://play.google.com/store/apps/details?id=host.exp.exponent))
2. Run `npm start`
3. Scan QR code with your phone

**Option 2: iOS Simulator (macOS only)**
```bash
npm run ios
```

**Option 3: Android Emulator**
```bash
npm run android
```

**Option 4: Web (for testing only)**
```bash
npm run web
```

## 📂 Project Structure

```
ClassBridgeMobile/
├── src/
│   ├── api/                 # API client & endpoints
│   │   ├── client.ts        # Axios instance with JWT interceptor
│   │   └── endpoints/       # API endpoint functions
│   ├── screens/             # Screen components
│   │   ├── auth/           # Login, Register
│   │   ├── parent/         # Parent-specific screens
│   │   ├── student/        # Student-specific screens
│   │   ├── teacher/        # Teacher-specific screens
│   │   └── common/         # Shared screens (Profile, Settings)
│   ├── components/          # Reusable UI components
│   ├── navigation/          # React Navigation setup
│   ├── context/            # React Context providers (Auth, Theme)
│   ├── hooks/              # Custom React hooks
│   ├── services/           # Push notifications, analytics
│   ├── types/              # TypeScript type definitions
│   └── utils/              # Helper functions
├── App.tsx                 # App entry point
├── app.json                # Expo configuration
├── package.json
└── tsconfig.json

Shared Code (with web app):
../shared/                  # Code shared between web and mobile
  ├── api/                  # API client (70% reused!)
  ├── types/                # TypeScript interfaces
  ├── hooks/                # React Query hooks
  └── utils/                # Validation, formatting
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file (ignored by git):

```bash
# API Base URL
API_URL=https://www.classbridge.ca/api

# Firebase (for push notifications)
FIREBASE_API_KEY=your_firebase_api_key
FIREBASE_PROJECT_ID=classbridge
```

### TypeScript Path Aliases

```typescript
// Import from src
import { AuthContext } from '@/context/AuthContext';

// Import from shared code
import { apiClient } from '@shared/api/client';
```

## 🛠️ Development

### Code Style

This project uses ESLint and Prettier for code formatting.

```bash
# Lint code
npm run lint

# Format code
npm run format
```

### Type Checking

```bash
# Run TypeScript compiler
npx tsc --noEmit
```

## 🧪 Testing

```bash
# Run tests (when implemented)
npm test

# Run with coverage
npm test -- --coverage
```

## 📱 Key Features

### Authentication
- Login/Register with JWT tokens
- Token refresh on expiry
- Secure token storage with AsyncStorage
- Role-based navigation

### Push Notifications
- Firebase Cloud Messaging integration
- Background notification handling
- Deep linking to specific screens
- Local notifications

### Offline Support
- React Query cache persistence
- Optimistic updates
- Queue mutations for sync when online

### Role-Based Dashboards
- **Students:** View assignments, submit work, check grades
- **Parents:** Monitor children's progress, message teachers
- **Teachers:** Manage courses, grade assignments, communicate
- **Admins:** System oversight and analytics

## 🔐 API Integration

The mobile app connects to the ClassBridge backend API:

**Base URL:** `https://www.classbridge.ca/api`

**Authentication:**
- JWT tokens stored in AsyncStorage
- Axios interceptor adds Bearer token to all requests
- Auto-refresh on 401 errors

**Example:**
```typescript
import { apiClient } from '@/api/client';

// Authenticated request
const courses = await apiClient.get('/courses');
```

## 📦 Building for Production

### Android

```bash
# Build APK
expo build:android -t apk

# Build AAB (for Google Play)
expo build:android -t app-bundle
```

### iOS

```bash
# Build for App Store
expo build:ios -t archive

# Build for simulator
expo build:ios -t simulator
```

### Using EAS Build (Recommended)

```bash
# Install EAS CLI
npm install -g eas-cli

# Configure project
eas build:configure

# Build for both platforms
eas build --platform all
```

## 🚢 Deployment

### TestFlight (iOS Beta)
1. Build with `expo build:ios`
2. Upload to App Store Connect
3. Invite testers via TestFlight

### Google Play Internal Testing (Android Beta)
1. Build with `expo build:android -t app-bundle`
2. Upload to Google Play Console
3. Create internal testing track
4. Invite testers

## 🔗 Related Documentation

- [Backend API Docs](http://localhost:8000/docs) (Swagger)
- [Mobile Development Guide](../MOBILE_DEV_GUIDE.md)
- [Mobile Strategy](../MOBILE_STRATEGY.md)
- [Implementation Plan](../MOBILE_IMPLEMENTATION_PLAN.md)

## 📋 Development Checklist

- [x] Project initialized with Expo
- [x] Dependencies installed
- [x] Folder structure created
- [x] TypeScript configured
- [x] ESLint/Prettier configured
- [ ] Authentication flow implemented
- [ ] Navigation setup complete
- [ ] API integration working
- [ ] Push notifications configured
- [ ] All screens implemented
- [ ] Tests written
- [ ] Production build tested

## 🐛 Troubleshooting

### Metro Bundler Issues
```bash
# Clear cache
npx expo start -c
```

### iOS Pod Issues
```bash
cd ios
pod deintegrate
pod install
cd ..
```

### Android Build Issues
```bash
cd android
./gradlew clean
cd ..
```

### Module Not Found
```bash
# Clear watchman
watchman watch-del-all

# Reinstall dependencies
rm -rf node_modules
npm install
```

## 📞 Support

For issues or questions:
- Check [GitHub Issues](https://github.com/theepangnani/emai-dev-03/issues?q=label%3Amobile)
- Review [MOBILE_DEV_GUIDE.md](../MOBILE_DEV_GUIDE.md)
- Contact: development team

## 📄 License

Private - ClassBridge Education Platform

---

**Status:** ✅ Setup Complete - Ready for Development

**Next Steps:**
1. Implement authentication flow ([Issue #325](https://github.com/theepangnani/emai-dev-03/issues/325))
2. Set up navigation ([Issue #326](https://github.com/theepangnani/emai-dev-03/issues/326))
3. Build core screens (Issues #327-#334)

Last updated: 2026-02-14
