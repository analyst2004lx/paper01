import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Arrow

fig, ax = plt.subplots(figsize=(6,3))
ax.axis('off')

# Draw three boxes representing system components
boxes = [((0.05,0.25), 0.25, 0.5, 'Scheduler'),
         ((0.375,0.25), 0.25, 0.5, 'Factory'),
         ((0.7,0.25), 0.25, 0.5, 'Processes')]

for (x,y), w, h, label in boxes:
    rect = FancyBboxPatch((x,y), w, h, boxstyle='round,pad=0.02', linewidth=1.2,
                         edgecolor='black', facecolor='#e6f2ff')
    ax.add_patch(rect)
    ax.text(x+w/2, y+h/2, label, ha='center', va='center', fontsize=12)

# Draw arrows between boxes
ax.annotate('', xy=(0.325,0.5), xytext=(0.35,0.5), arrowprops=dict(arrowstyle='->', lw=1.5))
ax.annotate('', xy=(0.65,0.5), xytext=(0.675,0.5), arrowprops=dict(arrowstyle='->', lw=1.5))

ax.set_xlim(0,1)
ax.set_ylim(0,1)

plt.savefig('figures/fig_system_model.pdf', bbox_inches='tight')
plt.savefig('figures/fig_system_model.png', bbox_inches='tight', dpi=150)
print('Generated figures/fig_system_model.pdf and .png')
