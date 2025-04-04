import pygame
import requests
import io
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

# Image URLs to preload
image_urls = [
    "https://512pixels.net/downloads/macos-wallpapers-thumbs/10-0_10.1--thumb.png",
    "https://512pixels.net/downloads/macos-wallpapers-thumbs/10-2--thumb.png",
    "https://512pixels.net/downloads/macos-wallpapers-thumbs/10-3--thumb.png",
]

# Global variables
current_image_index = 0
preloaded_images = []
screen = None
running = True
button1_previous = 0
button2_previous = 0

# Create a command queue for thread-safe communication
command_queue = queue.Queue()

def download_and_preload_images():
    """Download and preload all images"""
    global preloaded_images
    
    print("Preloading images...")
    for i, url in enumerate(image_urls):
        try:
            print(f"Downloading image {i+1}/{len(image_urls)}: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            # Convert to pygame image
            image_file = io.BytesIO(response.content)
            image = pygame.image.load(image_file)
            preloaded_images.append(image)
            print(f"Successfully loaded image {i+1}")
        except Exception as e:
            print(f"Error downloading image {i+1}: {e}")
            # Add a blank image as a placeholder
            blank = pygame.Surface((800, 600))
            blank.fill((0, 0, 0))
            preloaded_images.append(blank)
            
    print(f"Preloaded {len(preloaded_images)} images")

def display_current_image():
    """Display the current image on the screen"""
    global screen, current_image_index, preloaded_images
    
    if not preloaded_images:
        return
    
    # Get the current image
    image = preloaded_images[current_image_index]
    
    # Get screen dimensions
    screen_width = screen.get_width()
    screen_height = screen.get_height()
    
    # Scale image to fit screen
    img_width, img_height = image.get_size()
    scale_factor = min(screen_width / img_width, screen_height / img_height)
    new_width = int(img_width * scale_factor)
    new_height = int(img_height * scale_factor)
    scaled_image = pygame.transform.scale(image, (new_width, new_height))
    
    # Calculate position to center the image
    x_pos = (screen_width - new_width) // 2
    y_pos = (screen_height - new_height) // 2
    
    # Fill the screen with black
    screen.fill((0, 0, 0))
    
    # Draw the image on the screen
    screen.blit(scaled_image, (x_pos, y_pos))
    
    # Update display
    pygame.display.flip()
    
    print(f"Displaying image {current_image_index + 1}/{len(preloaded_images)}")

def next_image():
    """Switch to the next image"""
    global current_image_index, preloaded_images
    
    if not preloaded_images:
        return
        
    current_image_index = (current_image_index + 1) % len(preloaded_images)
    # Queue a display update instead of calling directly
    command_queue.put("display")

def previous_image():
    """Switch to the previous image"""
    global current_image_index, preloaded_images
    
    if not preloaded_images:
        return
        
    current_image_index = (current_image_index - 1) % len(preloaded_images)
    # Queue a display update instead of calling directly
    command_queue.put("display")

def monitor_buttons():
    """Monitor GPIO button states in a separate thread"""
    global running, button1_previous, button2_previous
    
    print(f"Monitoring GPIO pins {button1_pin} and {button2_pin}")
    
    while running:
        try:
            # Read current button states
            button1_current = GPIO.input(button1_pin)
            button2_current = GPIO.input(button2_pin)
            
            # Check if button1 was just pressed (transition from 0 to 1)
            if button1_current == 1 and button1_previous == 0:
                print("Button 1 pressed - Next image")
                # Queue a command instead of calling function directly
                command_queue.put("next")
                
            # Check if button2 was just pressed (transition from 0 to 1)
            if button2_current == 1 and button2_previous == 0:
                print("Button 2 pressed - Previous image")
                # Queue a command instead of calling function directly
                command_queue.put("previous")
                
            # Update previous states
            button1_previous = button1_current
            button2_previous = button2_current
            
            # Small delay to prevent CPU hogging
            time.sleep(0.1)
        except Exception as e:
            print(f"Error in button monitoring thread: {e}")
            time.sleep(1)  # Add a longer delay if there's an error

def main():
    global screen, running
    
    # Initialize pygame
    pygame.init()
    
    # Hide mouse cursor
    pygame.mouse.set_visible(False)
    
    # Get the screen info
    screen_info = pygame.display.Info()
    screen_width = screen_info.current_w
    screen_height = screen_info.current_h
    
    # Set up the display
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
    pygame.display.set_caption("RPi Image Viewer")
    
    # Download and preload images
    download_and_preload_images()
    
    # Start the button monitoring thread
    button_thread = threading.Thread(target=monitor_buttons)
    button_thread.daemon = True
    button_thread.start()
    
    # Display the first image
    display_current_image()
    
    # Main loop
    try:
        while running:
            # Check for pygame events
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
            
            # Check the command queue (non-blocking)
            try:
                command = command_queue.get_nowait()
                if command == "next":
                    next_image()
                elif command == "previous":
                    previous_image()
                elif command == "display":
                    display_current_image()
                command_queue.task_done()
            except queue.Empty:
                pass  # No commands in the queue
            
            # Small delay to prevent CPU hogging
            time.sleep(0.05)
    
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
