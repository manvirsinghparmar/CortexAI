# CortexAI Chat UI

A modern, beautiful chat interface inspired by premium AI chat applications.

## Features

- 🎨 **Modern Design**: Clean, minimalist interface with subtle gradient effects
- 🌟 **Premium Aesthetics**: Smooth animations, hover effects, and micro-interactions
- 📱 **Responsive**: Works seamlessly on desktop, tablet, and mobile devices
- ⌨️ **Keyboard Shortcuts**: Quick access with Ctrl/Cmd + K to focus search
- 🎯 **Interactive Examples**: Click on example queries to populate the search box
- 🔄 **Model Selection**: Switch between different AI models
- 📎 **File Attachments**: Support for uploading files
- 🎤 **Voice Input**: Microphone support for voice queries
- 🌐 **Multi-language**: Language selector for internationalization

## Quick Start

### Option 1: Open Directly in Browser

1. Navigate to the `ui` folder
2. Double-click `index.html` to open in your default browser

### Option 2: Use a Local Server (Recommended)

Using Python:
```bash
cd "c:\Users\Soumadeep Gupta\CortexAI\CortexAI\ui"
python -m http.server 8000
```

Then open your browser to: `http://localhost:8000`

Using Node.js (if you have npx):
```bash
cd "c:\Users\Soumadeep Gupta\CortexAI\CortexAI\ui"
npx serve
```

### Option 3: Use Live Server (VS Code Extension)

1. Install the "Live Server" extension in VS Code
2. Right-click on `index.html`
3. Select "Open with Live Server"

## File Structure

```
ui/
├── index.html      # Main HTML structure
├── styles.css      # Complete styling with design tokens
├── script.js       # Interactive functionality
└── README.md       # This file
```

## Design Features

### Color Palette
- **Background**: Light gray (#f5f5f5) with white cards
- **Accent**: Black for buttons and important elements
- **Glow Effect**: Warm yellow/golden gradient for visual interest
- **Text**: Hierarchical grays for readability

### Typography
- **Font Family**: Inter (Google Fonts)
- **Headings**: 600 weight, large sizes for impact
- **Body**: 400-500 weight for readability

### Interactions
- **Hover Effects**: Subtle background changes and transforms
- **Click Animations**: Scale effects for tactile feedback
- **Smooth Transitions**: 150-350ms for polished feel
- **Focus States**: Enhanced borders and shadows

## Keyboard Shortcuts

- `Ctrl/Cmd + K`: Focus search input
- `Escape`: Clear search and blur input
- `Enter`: Submit query

## Customization

### Changing Colors
Edit the CSS variables in `styles.css`:
```css
:root {
    --color-accent: #000000;  /* Change accent color */
    --color-glow-start: rgba(255, 220, 120, 0.3);  /* Adjust glow */
}
```

### Adding More Examples
Edit the HTML in `index.html` to add more example queries:
```html
<button class="example-item" data-query="Your query here">
    <span>Your query here</span>
    <svg>...</svg>
</button>
```

## Integration with CortexAI Backend

To connect this UI to your CortexAI backend:

1. Update the `handleSubmit()` function in `script.js`
2. Replace the alert with an API call:

```javascript
const handleSubmit = async () => {
    const query = searchInput.value.trim();
    if (query) {
        try {
            const response = await fetch('YOUR_API_ENDPOINT', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query })
            });
            const data = await response.json();
            // Handle response
        } catch (error) {
            console.error('Error:', error);
        }
    }
};
```

## Browser Compatibility

- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Mobile browsers

## Next Steps

1. **Add Chat History**: Display previous conversations
2. **Streaming Responses**: Show AI responses as they're generated
3. **Dark Mode**: Add theme toggle
4. **User Profiles**: Add authentication and user settings
5. **Advanced Features**: Code highlighting, markdown rendering, etc.

## License

Part of the CortexAI project.
