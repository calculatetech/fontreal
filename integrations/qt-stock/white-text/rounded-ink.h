// Balance isolated thin sections by the area of the fitted outline in each cell.
void restoreRoundEdges(std::vector<fontreal_v3::Coverage> &values,
                       const fontreal_v3::OutlineSamples &outline, fontreal_v3::Ink ink, QByteArray &aligned, int mode)
{
    using namespace fontreal_v3;
    const int width=outline.frame.width, height=outline.frame.height;
    for (int y=1; y<height-1; ++y) {
        for (int x=0; x<width;) {
            if (outline.center(x,y)<5) {
                ++x;
                continue;
            }
            const int left=x++;
            while (x<width && outline.center(x,y)>=5)
                ++x;
            const int right=x;
            if (right-left>3)
                continue;
            double mass=0, current=0;
            bool protectedSection=false;
            for (int col=left; col<right; ++col) {
                const int i=y*width+col;
                mass+=outline.center(col,y)/255.;
                current+=linearInk(values[i],ink);
                protectedSection|=aligned[i] || values[i]>=245;
            }
            if (protectedSection || mass<.53 || mass>1.10)
                continue;
            const auto neighbor=[&](int row) {
                for (int col=std::max(0,left-1); col<std::min(width,right+1); ++col)
                    if (outline.center(col,row)>=72)
                        return true;
                return false;
            };
            if (!neighbor(y-1) || !neighbor(y+1))
                continue;
            const double cap=ink==Ink::Light ? .99*mass+.045 : (mode>=9 ? 1.49 : 1.36)*mass+.025;
            // Leave a modest part of the original treatment to carry the stroke through a bend.
            const double density=std::min(current,cap);
            for (int col=left; col<right; ++col) {
                const int i=y*width+col;
                const double exact=density*outline.center(col,y)/(255*mass);
                const double old=linearInk(values[i],ink);
                values[i]=encodedInk(.82*exact+.18*old,ink);
                aligned[i]=char(255);
            }
        }
    }
}
