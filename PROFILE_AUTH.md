# Profile & Authentication System

## Overview

The FusionTech Systems Dashboard includes a lightweight employee profile system that enables:
- User identification via email (@fusiontech.com domain required)
- Department-based access (scaffolding for future department-specific dashboards)
- Profile management
- Session persistence

## Email Domain Requirement

**All users must use @fusiontech.com email addresses.**

The system enforces this at both frontend and backend levels:
- Frontend validation prevents submission of non-FusionTech emails
- Backend validation returns error if domain doesn't match
- Error message: "Please use your FusionTech Systems company email."

## Database Setup

### Running Migrations

The system uses an idempotent migration approach. All database migrations live in:
```
Dataset_Scripts/Hosted_SQL_Scripts/
```

#### Automatic Migration Runner

To run all migrations in order:

```bash
cd Dataset_Scripts/Hosted_SQL_Scripts/
python run_migrations.py
```

This script:
- Checks which migrations have already been applied
- Runs only new migrations
- Tracks applied migrations in the `schema_migrations` table
- Is safe to run multiple times

#### Manual Migration

To run a single migration manually:

```bash
cd Dataset_Scripts/Hosted_SQL_Scripts/
python create_users_table.py
```

### Database Tables Created

1. **`schema_migrations`** - Tracks applied migrations
2. **`departments`** - Reference table for valid departments
3. **`users`** - Employee profiles with department associations

### Seeded Departments

The following departments are automatically created:
- Marketing (`MARKETING`)
- Sales (`SALES`)
- Finance (`FINANCE`)
- Engineering & IT (`ENGINEERING_IT`)
- Supply Chain / Global Operations (`SUPPLY_CHAIN`)
- Customer Support / Customer Success (`CUSTOMER_SUPPORT`)
- Security (`SECURITY`)

## User Flow

### First-Time Users

1. Navigate to the dashboard
2. System redirects to login page
3. Enter FusionTech email address (@fusiontech.com)
4. System checks if profile exists:
   - **Exists**: Logs in and redirects to dashboard
   - **Does not exist**: Shows "Account not found" message with "Create Account" button
5. Click "Create Account" button
6. Complete profile form (first name, last name, department, optional sub-department & location)
7. Submit to create profile and redirect to dashboard

**Alternative**: Click "Don't have an account? Create an account" link at bottom of login form to go directly to registration.

### Existing Users

1. Navigate to dashboard
2. Enter FusionTech email
3. Automatically logged in and redirected

### Profile Management

Users can edit their profile at any time:

1. Click the profile icon in the top-right corner
2. Select "Edit Profile" from the dropdown
3. Update fields
4. Click "Save Changes"

### Sign Out

Click profile icon → "Sign Out"

This clears the session but preserves the profile in the database.

## Department-Specific Dashboards (Scaffolding)

### Current Implementation

The codebase includes infrastructure for department-specific filtering:

**Backend** (`Flask_API.py`):
```python
def filter_by_department(data, user):
    """Filter dashboard data by user's department.
    
    TODO: Implement department-specific filtering:
    - Marketing: Focus on trends, summary metrics
    - Engineering: Product quality signals, technical issues
    - Finance: Revenue risk, KPI rollups
    - Customer Support: Complaint themes, response times
    """
    return data  # Currently returns unfiltered data
```

**Usage in API Routes**:
```python
@app.route("/api/dashboard")
@require_profile
def api_dashboard():
    user = get_current_user()
    risk = artifacts['risk_results']
    
    # TODO: Apply department-specific filtering here
    # risk = filter_by_department(risk, user)
    
    # ... rest of logic
```

### Future Department Views

When implementing department-specific views:

1. **Marketing**: Aggregate sentiment trends, high-level KPIs, summary cards
2. **Engineering**: Deep-dive into complaint themes, technical issue tracking, product-specific risk
3. **Finance**: Revenue impact calculations, cost analysis, risk-adjusted forecasts
4. **Customer Support**: Complaint theme trends, response-time analytics, escalation tracking
5. **Sales**: Product performance metrics, competitive signals, customer sentiment
6. **Supply Chain**: Product quality signals, defect trends, supplier issues
7. **Security**: Security-related complaint detection, vulnerability mentions

To enable:
1. Uncomment the filtering line in `api_dashboard()`
2. Implement logic inside `filter_by_department()`
3. Optionally create department-specific API endpoints
4. Update frontend to request department-filtered data

## API Endpoints

### Authentication & Profile

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | GET | Login/registration page |
| `/api/check_email` | POST | Check if email exists |
| `/api/register` | POST | Create new user profile |
| `/api/profile` | GET | Get current user profile |
| `/api/profile` | PUT | Update user profile |
| `/api/departments` | GET | List all departments |
| `/logout` | GET | Clear session and sign out |

### Protected Routes

All dashboard API routes now require authentication via the `@require_profile` decorator:
- `/api/dashboard`
- `/api/products`
- `/api/products/<asin>`
- `/api/trends`
- `/api/analyze`
- `/api/chatbot`

## Session Management

- Sessions use Flask's built-in session mechanism
- Session secret key: Set via `FLASK_SECRET_KEY` environment variable (defaults to `dev-secret-key-change-in-production`)
- User identity stored in `session['user_email']`
- **Important**: Set a secure secret key in production!

## Security Notes

### Current Implementation (Lightweight)

This is **not** full OAuth/SSO authentication. It's a lightweight profile capture system suitable for internal tools.

**What it provides:**
- Session-based access control
- Email-based identity
- Profile persistence

**What it does NOT provide:**
- Password authentication
- Multi-factor authentication
- SSO integration
- Password reset flows

### Production Recommendations

For production deployment:

1. **Set secure session secret**:
   ```bash
   export FLASK_SECRET_KEY="your-secure-random-key-here"
   ```

2. **Consider adding**:
   - HTTPS enforcement
   - Session timeout
   - CSRF protection
   - Rate limiting on login endpoints

3. **For enterprise deployment**:
   - Integrate with FusionTech SSO/SAML
   - Use OAuth 2.0 / OpenID Connect
   - Add role-based access control (RBAC)

## Helper Functions

### Neon Database Helpers

New functions in `Neon_Accessibility_Helper_Functions.py`:

```python
# Get user by email
user = get_user_by_email(email, conn)

# Create new user
user = create_user(first_name, last_name, email, department, sub_department, location, conn)

# Update user profile
success = update_user(email, first_name, last_name, department, sub_department, location, conn)

# Get departments list
departments = get_departments(conn)
```

## Testing

### Manual Test Checklist

- [ ] Fresh database: Run migrations successfully
- [ ] Access dashboard without login → redirects to login page
- [ ] Enter new email → shows registration form
- [ ] Complete registration → creates profile and redirects to dashboard
- [ ] Sign out → clears session
- [ ] Enter existing email → logs in without registration
- [ ] Edit profile → updates database and UI
- [ ] Profile dropdown shows correct user info
- [ ] All dashboard features work after login

### Sample Manual Test Flow

```bash
# 1. Run migrations
cd Dataset_Scripts/Hosted_SQL_Scripts/
python run_migrations.py

# 2. Start app
cd ../../src/
python Run_System.py

# 3. Navigate to http://localhost:5050
# 4. Enter test@fusiontech.com
# 5. Click "Create Account" button (appears after "Account not found" message)
# 6. Fill registration form
# 7. Verify dashboard loads with profile dropdown
# 8. Click profile icon → Edit Profile
# 9. Change name, save
# 9. Verify name updates in header
# 10. Sign out
# 11. Log back in with same email
# 12. Verify profile persisted
```

## Files Modified/Created

### New Files
- `Dataset_Scripts/Hosted_SQL_Scripts/create_users_table.py` - Migration script
- `Dataset_Scripts/Hosted_SQL_Scripts/run_migrations.py` - Migration runner
- `src/templates/login.html` - Login/registration page
- `PROFILE_AUTH.md` - This documentation

### Modified Files
- `src/Flask_API.py` - Added session management, profile routes, decorators
- `src/Neon_Accessibility_Helper_Functions.py` - Added user management functions
- `src/templates/Dashboard.html` - Added profile dropdown and edit modal
- `src/static/dashboard.css` - Added profile UI styling
- `src/static/dashboard.js` - Added profile dropdown and edit functionality

## Environment Variables

Ensure your `.env` file includes:

```env
DATABASE_URL=postgresql://...
FLASK_SECRET_KEY=your-secure-secret-key-here  # Required for sessions
```

## Troubleshooting

### "Users table already exists" on migration
This is normal if you've run the migration before. The script is idempotent and won't duplicate tables.

### Login page doesn't redirect after successful login
Check browser console for JavaScript errors. Ensure `/api/check_email` is returning `{"status": "success", "exists": true}`.

### Profile dropdown not showing
Check that:
1. User data is passed to template: `render_template("Dashboard.html", user=user)`
2. CSS for `.profile-dropdown` is loaded
3. Browser console shows no JavaScript errors

### Session not persisting
Verify `FLASK_SECRET_KEY` is set. Without it, sessions may not work correctly.

### Department dropdown empty
Check that:
1. Migration ran successfully and seeded `departments` table
2. `/api/departments` endpoint returns data
3. Browser can reach the endpoint (check Network tab in dev tools)

## Future Enhancements

Planned improvements for department-specific dashboards:

1. **Department View Toggle**: UI switch to enable/disable department filtering
2. **Custom KPI Cards**: Show different metrics per department
3. **Filtered Alerts**: Show only alerts relevant to user's department
4. **Department Dashboards**: Separate pages/views per department
5. **Role-Based Access**: Restrict certain features to specific departments
6. **Activity Logging**: Track user actions per department
7. **Notification Preferences**: Department-specific alert settings

---

**Questions or Issues?**  
Contact: FusionTech Systems Support Team
