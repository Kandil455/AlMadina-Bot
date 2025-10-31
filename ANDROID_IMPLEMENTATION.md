# AlMadina Android App Implementation

## Overview

This is the Android implementation of the AlMadina bot transformed into a beautiful, performant Android application with smooth UI, 3D design elements, and seamless content processing.

**Technology Stack:**
- **Language:** Kotlin (latest stable)
- **UI Framework:** Jetpack Compose
- **Architecture:** MVVM with Clean Architecture
- **Minimum API Level:** 26 (Android 8.0)
- **Target API Level:** 34 (Android 14)

## Project Structure

```
app/src/
├── main/
│   ├── kotlin/com/almadina/app/
│   │   ├── MainActivity.kt
│   │   ├── AlMadinaApplication.kt
│   │   ├── di/
│   │   │   └── AppModule.kt (Hilt configuration)
│   │   ├── data/
│   │   │   ├── local/
│   │   │   │   ├── database/ (Room entities and DAOs)
│   │   │   │   └── preferences/ (DataStore)
│   │   │   ├── remote/
│   │   │   │   ├── api/ (Retrofit service)
│   │   │   │   └── model/ (Request/Response DTOs)
│   │   │   └── repository/ (DocumentRepository)
│   │   ├── domain/
│   │   │   └── models/
│   │   ├── presentation/
│   │   │   ├── navigation/ (Compose Navigation routes)
│   │   │   ├── ui/
│   │   │   │   ├── screens/ (Dashboard, Upload, Results, Settings, Processing)
│   │   │   │   ├── components/ (FeatureCard, etc.)
│   │   │   │   └── theme/ (Material Design 3 theme)
│   │   │   └── viewmodel/ (DocumentViewModel, SettingsViewModel)
│   │   └── utils/
│   │       ├── PdfGenerator.kt
│   │       ├── FileUtils.kt
│   │       └── ErrorHandler.kt
│   └── res/
│       ├── values/ (strings, colors, themes)
│       └── xml/ (file_paths, data_extraction_rules)
└── test/
    └── kotlin/com/almadina/app/
        ├── presentation/viewmodel/
        ├── data/repository/
        └── data/remote/api/
```

## Core Features

### 1. Document Summarization
- **File Input:** PDF, images (JPG, PNG), text files
- **File Size Limit:** 10MB maximum
- **Processing Timeout:** 60 seconds
- **Response Format:** HTML formatted output
- **API Endpoint:** `POST /api/v1/summarize`

**Request Body:**
```json
{
  "document_type": "pdf|image|text",
  "content": "base64_encoded_or_text",
  "model": "gemini-2.0-flash",
  "style": "brief|complete"
}
```

### 2. Content Explanation
- **Personas:** Professor (academic, detailed), Friend (simplified, encouraging), Coach (key takeaways, actionable)
- **Languages:** English, العربية (Arabic), Bilingual
- **Output Format:** Structured HTML with sections, definitions, examples
- **Caching:** Recent explanations stored locally for offline access
- **API Endpoint:** `POST /api/v1/explain`

**Request Body:**
```json
{
  "document_type": "pdf|image|text",
  "content": "base64_encoded_or_text",
  "model": "gemini-2.0-flash",
  "persona": "professor|friend|coach",
  "language": "en|ar|bilingual"
}
```

### 3. PDF Download
- **PDF Library:** iText (Android PDF generation)
- **Styling:** Preserved from HTML output
- **Naming:** Automatic with timestamp (e.g., "almadina_2025-01-15_14-30.pdf")
- **Storage:** Device Downloads folder
- **Permissions:** WRITE_EXTERNAL_STORAGE required

## Settings & Configuration

### User Preferences (DataStore)
- **API Base URL:** Configurable at runtime
- **AI Model Selection:** Dropdown with gemini-2.0-flash (default), gemini-1.5-flash, gemini-1.5-pro, or custom
- **Language Preference:** English, العربية, or Bilingual
- **Cache Management:** View size, auto-clear option
- **Theme:** Light, Dark, or System default

## API Integration

### Retrofit Configuration
- **Base URL:** From DataStore (or provided default)
- **Timeout:** 60 seconds for document processing
- **Retry Policy:** 2 retries for transient errors
- **Interceptor:** Adds `X-AI-Model` header with current model from DataStore

### Error Handling
- **400 Bad Request:** "Invalid input. Check file format and size."
- **401 Unauthorized:** "Session expired. Please log in again."
- **429 Too Many Requests:** "Rate limit exceeded. Please wait before trying again."
- **500 Internal Server Error:** "Server error. Please try again later."
- **Network errors:** "No internet connection. Check your network."
- **Timeout errors:** "Request took too long. Please try again."

## Database (Room)

### Processing History Table
- `id`: PRIMARY KEY (auto-generated)
- `documentContent`: String (first 100 chars for reference)
- `operationType`: String ("summarize" or "explain")
- `result`: String (formatted HTML)
- `createdAt`: Long (timestamp)
- `processingTimeMs`: Long (optional)
- `filePath`: String (optional)

## User Interface

### Screens
1. **Dashboard:** Features cards with gradient backgrounds and 3D effects
2. **Upload:** Document selection with file picker integration
3. **Processing:** Loading screen with 3D rotating spinner
4. **Results:** HTML-rendered content display with download/share options
5. **Settings:** API config, model selection, cache management

### UI Components
- **FeatureCard:** Reusable card component with gradients and shadows
- **Material Design 3:** Modern, accessible design system
- **Animations:** Smooth transitions and micro-interactions
- **3D Effects:** Rotating spinners, perspective transforms, parallax

## Development Setup

### Requirements
- Android Studio (2023.1 or later)
- Android SDK 34
- Gradle 8.0 or later
- Kotlin 1.9.22

### Build and Run
```bash
# Build the project
./gradlew build

# Run on emulator/device
./gradlew installDebug

# Run tests
./gradlew test

# Build release APK
./gradlew assembleRelease
```

## Dependencies

### Core Dependencies
- Jetpack Compose (Material 3)
- Retrofit 2 & OkHttp 4
- Room Database
- DataStore Preferences
- Hilt Dependency Injection
- Coroutines
- Coil (image loading)
- iText (PDF generation)
- Gson (JSON serialization)
- JSoup (HTML parsing)

### Testing
- JUnit 4
- MockK
- Kotlin Coroutines Test
- AndroidX Test

## Key Features Implementation

### Material Design 3 Compliance
- Color scheme with primary, secondary, tertiary colors
- Typography with proper font scales
- Dark mode support with dynamic theming
- Smooth animations and transitions

### 3D Visual Effects
- **Dashboard Cards:** Subtle perspective transform on press
- **Loading Spinner:** Continuous 3D rotation
- **Results Sections:** Parallax scroll effects

### Offline Support
- Local caching of recent summaries/explanations
- Cached indicator in results display
- Prevents document upload without internet connection

### Accessibility
- System font size support
- Content descriptors for interactive elements
- RTL support for Arabic content
- High contrast mode compatible

### Performance
- Asynchronous processing prevents UI blocking
- Debounced rapid taps
- Efficient database queries
- Optimized memory usage

## Testing

### Unit Tests
- `DocumentViewModelTest`: Tests summarize/explain flows, error handling
- `SettingsViewModelTest`: Tests settings persistence and retrieval
- `DocumentRepositoryTest`: Tests API integration and caching

### Running Tests
```bash
./gradlew test
```

## Security Considerations

- API endpoints validated as HTTPS
- Cleartext traffic disabled in production
- File permissions properly managed
- User credentials not stored locally
- API keys handled securely via BuildConfig

## Deployment

### Build Release APK
```bash
./gradlew bundleRelease
```

### Sign APK
```bash
jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 \
  -keystore key.jks app-release.aab release
```

### Play Store Preparation
- Minimum API 26 (Android 8.0)
- Target API 34 (Android 14)
- Target SDK 34 compliant
- Privacy policy required
- Permissions justified

## Future Enhancements

- Local ML models for offline summarization
- Advanced file picker with cloud storage integration
- Bookmarking and favorites system
- Export to multiple formats (Word, Markdown, etc.)
- Dark mode enhancements
- Voice input support
- Real-time collaboration

## Troubleshooting

### Build Issues
- Ensure Gradle and build tools are updated
- Clear cache: `./gradlew clean build`
- Check Android SDK versions

### Runtime Issues
- Check API endpoint configuration
- Verify internet connectivity
- Check file permissions on device
- Review error messages in Logcat

## Documentation References

- [Jetpack Compose](https://developer.android.com/jetpack/compose)
- [Material Design 3](https://m3.material.io/)
- [Android Architecture Guide](https://developer.android.com/architecture)
- [Room Persistence Library](https://developer.android.com/training/data-storage/room)
- [DataStore](https://developer.android.com/topic/libraries/architecture/datastore)
- [Hilt](https://developer.android.com/training/dependency-injection/hilt-android)

## License

This Android implementation is part of the AlMadina project.
