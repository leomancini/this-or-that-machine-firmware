import pygame
import sys
import os
import RPi.GPIO as GPIO
import time
import threading
import queue

# Clean up any previous configurations
try:
    GPIO.cleanup()
except:
    pass

# Use BCM numbering
GPIO.setmode(GPIO.BCM)

# Use GPIO 10 and GPIO 4
button1_pin = 10
button2_pin = 4  # Physical pin 7

# Setup pins
GPIO.setup(button1_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(button2_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Global variables
current_image_index = 0
image_paths = []  # Store paths instead of loaded images
current_image = None  # Only keep the currently displayed image in memory
screen = None
running = True
button1_previous = 0
button2_previous = 0
screen_width = 0
screen_height = 0
last_button_press_time = 0
debounce_time = 0.1  # Reduced debounce time for faster response

# Create a command queue for thread-safe communication
command_queue = queue.Queue()

def find_local_images():
    """Find all images in the images/ directory but don't load them yet"""
    global image_paths
    
    print("Finding local images...")
    
    # Create images directory if it doesn't exist
    if not os.path.exists("images"):
        os.makedirs("images")
        print("Created images/ directory. Please put your images there and restart.")
        return
    
    # Get all image files from the images directory
    valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp']  # Removed .gif to save memory
    
    for file in os.listdir("images"):
        if any(file.lower().endswith(ext) for ext in valid_extensions):
            image_paths.append(os.path.join("images", file))
    
    # Sort files alphabetically
    image_paths.sort()
    
    print(f"Found {len(image_paths)} images")

def load_current_image():
    """Load only the current image into memory"""
    global current_image, current_image_index, image_paths
    
    if not image_paths:
        # Create a simple blank image with text
        current_image = pygame.Surface((screen_width, screen_height))
        current_image.fill((0, 0, 0))
        font = pygame.font.Font(None, 36)
        text = font.render("No images found in images/ directory", True, (255, 255, 255))
        text_rect = text.get_rect(center=(screen_width//2, screen_height//2))
        current_image.blit(text, text_rect)
        return
    
    try:
        # Clear any previously loaded image to free memory
        current_image = None
        
        # Load the current image
        print(f"Loading image {current_image_index + 1}/{len(image_paths)}")
        img_path = image_paths[current_image_index]
        
        # Use convert to optimize the image format for display
        current_image = pygame.image.load(img_path).convert()
        
    except Exception as e:
        print(f"Error loading image: {e}")
        # Create an error image
        current_image = pygame.Surface((screen_width, screen_height))
        current_image.fill((0, 0, 0))
        font = pygame.font.Font(None, 36)
        text = font.render(f"Error loading image: {os.path.basename(img_path)}", True, (255, 0, 0))
        text_rect = text.get_rect(center=(screen_width//2, screen_height//2))
        current_image.blit(text, text_rect)

def display_current_image():
    """Display the current image on the screen with proper fullscreen handling"""
    global screen, current_image
    
    # First ensure we have the current image loaded
    if current_image is None:
        load_current_image()
    
    if current_image:
        # Fill the screen with black first
        screen.fill((0, 0, 0))
        
        # Get the current image dimensions
        img_width, img_height = current_image.get_size()
        
        # Calculate scale factor to fit screen while preserving aspect ratio
        # We want to FILL the screen, so we use max instead of min
        scale_factor = max(screen_width / img_width, screen_height / img_height)
        
        # Scale the image
        new_width = int(img_width * scale_factor)
        new_height = int(img_height * scale_factor)
        
        try:
            # Use smoothscale for better quality, but only for small images
            # For large images, use regular scale to improve performance
            if img_width * img_height < 1000000:  # Under 1 megapixel
                scaled_image = pygame.transform.smoothscale(current_image, (new_width, new_height))
            else:
                scaled_image = pygame.transform.scale(current_image, (new_width, new_height))
        except:
            # Fallback to regular scale if smoothscale fails
            scaled_image = pygame.transform.scale(current_image, (new_width, new_height))
        
        # Calculate position to center the image (this may place it partially offscreen)
        x_pos = (screen_width - new_width) // 2
        y_pos = (screen_height - new_height) // 2
        
        # Draw the image on the screen
        screen.blit(scaled_image, (x_pos, y_pos))
        
        # Display current image information
        font = pygame.font.Font(None, 24)
        info_text = f"{current_image_index + 1}/{len(image_paths)}"
        text_surface = font.render(info_text, True, (255, 255, 255))
        screen.blit(text_surface, (10, 10))
        
        # Update display
        pygame.display.flip()

def next_image():
    """Switch to the next image"""
    global current_image_index, image_paths, current_image
    
    if not image_paths:
        return
    
    # Free current image memory    
    current_image = None
        
    current_image_index = (current_image_index + 1) % len(image_paths)
    command_queue.put("display")

def previous_image():
    """Switch to the previous image"""
    global current_image_index, image_paths, current_image
    
    if not image_paths:
        return
    
    # Free current image memory
    current_image = None
        
    current_image_index = (current_image_index - 1) % len(image_paths)
    command_queue.put("display")

def monitor_buttons():
    """Monitor GPIO button states in a separate thread"""
    global running, button1_previous, button2_previous, last_button_press_time
    
    print(f"Monitoring GPIO pins {button1_pin} and {button2_pin}")
    
    while running:
        try:
            # Read current button states
            button1_current = GPIO.input(button1_pin)
            button2_current = GPIO.input(button2_pin)
            
            current_time = time.time()
            # Only process button presses if enough time has passed (debouncing)
            if current_time - last_button_press_time >= debounce_time:
                # Check if button1 was just pressed (transition from 0 to 1)
                if button1_current == 1 and button1_previous == 0:
                    print("Button 1 pressed - Next image")
                    # Use high priority for faster response
                    command_queue.put("next", block=False)
                    last_button_press_time = current_time
                    
                # Check if button2 was just pressed (transition from 0 to 1)
                if button2_current == 1 and button2_previous == 0:
                    print("Button 2 pressed - Previous image")
                    # Use high priority for faster response
                    command_queue.put("previous", block=False)
                    last_button_press_time = current_time
            
            # Update previous states
            button1_previous = button1_current
            button2_previous = button2_current
            
            # Shorter delay for faster button checks
            time.sleep(0.05)
        except Exception as e:
            print(f"Error in button monitoring thread: {e}")
            time.sleep(0.5)  # Shorter delay on error

def preload_next_images():
    """Preload next and previous images in the background to speed up navigation"""
    global image_paths, current_image_index
    
    if not image_paths or len(image_paths) <= 1:
        return
    
    # Calculate indexes of next and previous images
    next_idx = (current_image_index + 1) % len(image_paths)
    prev_idx = (current_image_index - 1) % len(image_paths)
    
    # Try to load these images in the background to have them in file cache
    try:
        # Just open and close the file to have it cached by the system
        with open(image_paths[next_idx], 'rb') as f:
            pass
        with open(image_paths[prev_idx], 'rb') as f:
            pass
    except Exception:
        pass  # Ignore any errors in preloading

def main():
    global screen, running, screen_width, screen_height
    
    # Initialize pygame with only the modules we need
    pygame.display.init()
    pygame.font.init()
    
    # Hide mouse cursor
    pygame.mouse.set_visible(False)
    
    # Get the current display size
    info = pygame.display.Info()
    screen_width = info.current_w
    screen_height = info.current_h
    
    # Try to set up the display in fullscreen mode
    try:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        screen_width = screen.get_width()
        screen_height = screen.get_height()
        print(f"Display initialized at {screen_width}x{screen_height}")
    except Exception as e:
        print(f"Error setting fullscreen mode: {e}")
        # Fallback to a smaller resolution if fullscreen fails
        screen_width = 640
        screen_height = 480
        screen = pygame.display.set_mode((screen_width, screen_height))
        print(f"Fallback display initialized at {screen_width}x{screen_height}")
    
    pygame.display.set_caption("RPi Image Viewer")
    
    # Find local images (but don't load them all yet)
    find_local_images()
    
    # Start the button monitoring thread with higher priority
    button_thread = threading.Thread(target=monitor_buttons)
    button_thread.daemon = True
    button_thread.start()
    
    # Display the first image
    load_current_image()
    display_current_image()
    
    # Start preloading neighboring images
    preload_thread = threading.Thread(target=preload_next_images)
    preload_thread.daemon = True
    preload_thread.start()
    
    # Main loop
    try:
        while running:
            # Process events quickly with minimal delay
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                        running = False
                    elif event.key == pygame.K_RIGHT or event.key == pygame.K_n:
                        next_image()
                    elif event.key == pygame.K_LEFT or event.key == pygame.K_p:
                        previous_image()
                    elif event.key == pygame.K_r:
                        # Reload image list
                        image_paths.clear()
                        find_local_images()
                        current_image_index = 0
                        load_current_image()
                        display_current_image()
                    elif event.key == pygame.K_f:
                        # Toggle fullscreen (might not work on all platforms)
                        pygame.display.toggle_fullscreen()
            
            # Check the command queue (non-blocking) with minimal delay
            try:
                command = command_queue.get_nowait()
                if command == "next":
                    next_image()
                elif command == "previous":
                    previous_image()
                elif command == "display":
                    load_current_image()
                    display_current_image()
                    # After displaying, start preloading the next ones for faster response
                    preload_thread = threading.Thread(target=preload_next_images)
                    preload_thread.daemon = True
                    preload_thread.start()
                command_queue.task_done()
            except queue.Empty:
                pass  # No commands in the queue
            
            # Very short delay to keep the CPU from maxing out
            # but still ensure quick button response
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\nExiting...")
    
    except Exception as e:
        print(f"Error in main loop: {e}")
    
    finally:
        # Clean up
        running = False
        pygame.quit()
        GPIO.cleanup()
        print("Cleanup complete")

if __name__ == "__main__":
    main()
